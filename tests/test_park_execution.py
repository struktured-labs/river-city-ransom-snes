import unittest
import tempfile
from pathlib import Path

from tools.audit_park_execution import packet_gaps, summarize, verify_ack_binding, sha


def row(frame, *, phase='park_00_right_run', scene='same', pause=False,
        transition=0, task=0xc0, room=3, nmi=None):
    ram=bytearray(2048)
    ram[0x42]=room
    ram[0x3f]=0x20 if pause else 0
    ram[0x100]=task
    return dict(frame=frame,phase=phase,scene_sha256=scene,
                game_ram_hex=ram.hex(),nmi_counter=frame if nmi is None else nmi,
                native=dict(pc=0xc7f2c9,task=task,guard=0,transition_state=transition),
                audio=dict(rms=100),fault=0)


def timing(first=2,last=4):
    return dict(absolute_completion_timing=dict(long_intervals=[dict(
        before=dict(frame=first),after=dict(frame=last),master_clocks=600000)]))


class ParkExecutionTests(unittest.TestCase):
    def test_final_hold_is_retained_and_ticks_not_called_frozen(self):
        report=summarize([row(f) for f in range(1,10)])
        self.assertEqual(report['scene_holds'][0]['frames'],9)
        self.assertEqual(report['scene_holds'][0]['nmi_advances'],8)
        self.assertNotIn('scene_stalls',report)

    def test_no_hold_spanning_different_inputs(self):
        rows=[row(f,phase='park_left_run' if f<=3 else 'park_right_run') for f in range(1,7)]
        self.assertEqual(summarize(rows)['scene_holds'],[])

    def test_pause_and_transition_pixels_excluded(self):
        for kw in ({'pause':True},{'transition':1},{'task':0},{'room':5}):
            self.assertEqual(summarize([row(f,**kw) for f in range(1,10)])['scene_holds'],[])

    def test_nmi_wrap_is_one_tick(self):
        result=summarize([row(1,nmi=65535),row(2,nmi=0)])
        self.assertEqual(result['nmi_step_histogram'],{1:1})

    def test_legacy_clock_rejected_explicitly(self):
        with self.assertRaisesRegex(ValueError,'absolute-clock'):
            packet_gaps([row(1)],{'absolute_completion_timing':None})

    def test_long_stable_packet_gap_requires_review(self):
        gaps=packet_gaps([row(f) for f in range(1,7)],timing())
        self.assertTrue(gaps[0]['stable_unpaused_park'])
        self.assertGreater(gaps[0]['nominal_frames'],1.5)

    def test_transition_on_boundary_excluded_from_stable_gate(self):
        for kw in ({'pause':True},{'transition':1},{'task':0},{'room':5}):
            rows=[row(f,**kw) if f==5 else row(f) for f in range(1,7)]
            self.assertFalse(packet_gaps(rows,timing())[0]['stable_unpaused_park'])

    def test_nonpark_gaps_do_not_count(self):
        rows=[row(f,phase='walk') for f in range(1,7)]
        self.assertEqual(packet_gaps(rows,timing()),[])

    def test_substituted_or_unbound_trace_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'ack.csv'
            path.write_text('original trace')
            receipt={'spc_ack_trace':{'sha256':sha(path)}}
            verify_ack_binding(receipt,path)
            path.write_text('other capture')
            for bad in (receipt,{}):
                with self.assertRaisesRegex(ValueError,'not bound'):
                    verify_ack_binding(bad,path)
