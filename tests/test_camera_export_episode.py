import unittest

from tools.audit_camera_export_episode import bracket, measure
from tools.camera_state_log import seed_bytes


def row(sequence, nmi, camera=0, display=None, served=None):
    return dict(sequence=sequence,nmi=nmi,room=0,working_camera=camera,
        committed_camera=camera,display_camera=camera if display is None else display,
        served_lo=(nmi//2 if served is None else served)&255,
        served_hi=(nmi//2 if served is None else served)>>8,
        fallback_lo=0,fallback_hi=0,nmi_changed_during_record=False)


def snapshot(count):
    data=bytearray(seed_bytes())
    data[8:12]=count.to_bytes(4,'little')
    data[12:14]=(0x6020+32*count).to_bytes(2,'little')
    for i in range(count):
        packet=bytearray(32)
        packet[:4]=i.to_bytes(4,'little')
        packet[4:6]=(2*i).to_bytes(2,'little')
        packet[27:29]=(2*i).to_bytes(2,'little')
        for b in packet[:30]:packet[30]^=b
        packet[31]=0xA5
        data[32*(i+1):32*(i+2)]=packet
    return bytes(data)


class CameraExportEpisodeTests(unittest.TestCase):
    def test_bracket_requires_new_unchanged_and_frozen_records(self):
        a,b=snapshot(1),snapshot(3)
        self.assertEqual([r['sequence'] for r in bracket(a,b,b)],[1,2])
        with self.assertRaises(ValueError):bracket(a,a,a)
        with self.assertRaises(ValueError):bracket(a,b,snapshot(4))
        altered=bytearray(b)
        altered[32+7]^=1;altered[32+30]^=1  # Valid XOR, but rewrites old data.
        with self.assertRaises(ValueError):bracket(a,bytes(altered),bytes(altered))

    def test_gaps_never_become_covered_two_tick_samples(self):
        result=measure([row(4,10),row(5,12,2,0),row(6,22,8,6)])
        self.assertEqual(result['adjacent_two_tick_samples'],1)
        self.assertEqual(result['adjacent_display_mismatches'],[])
        self.assertEqual(len(result['unobserved_intervals']),1)
        self.assertEqual(result['served_counter_ratio_exceptions'],[])

    def test_stale_shadow_and_missing_service_are_retained(self):
        result=measure([row(0,10,2),row(1,12,4,0,5)])
        self.assertEqual(len(result['adjacent_display_mismatches']),1)
        self.assertEqual(len(result['served_counter_ratio_exceptions']),1)

    def test_counter_wrap_and_bad_order(self):
        a,b=row(0,65534,served=65535),row(1,0,served=0)
        self.assertEqual(measure([a,b])['elapsed_nmi'],2)
        for bad in ([a,a],[b,a],[row(0,10),row(1,8)]):
            with self.assertRaises(ValueError):measure(bad)
