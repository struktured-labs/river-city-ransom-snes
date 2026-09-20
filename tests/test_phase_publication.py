import copy
import unittest

from tools.audit_phase_publication import equivalent, store_mismatches


class PhasePublicationTests(unittest.TestCase):
    def test_observer_neutrality_requires_complete_matching_core_and_data(self):
        receipt = dict(capture_complete=True,rom_sha256='rom',audio_sha256='pcm',
                       scenario_sha256='input',frames=2,core_sha256='core')
        rows = [dict(fault=0,input_requested=[7],input_delivered=[7])]
        equivalent(receipt,rows,receipt,rows,True)
        for field in receipt:
            bad = dict(receipt)
            bad[field] = False if field == 'capture_complete' else 'different'
            with self.assertRaises(ValueError, msg=field):
                equivalent(receipt,rows,bad,rows,True)
        bad = dict(receipt,core_sha256='other-core')
        equivalent(receipt,rows,bad,rows,False)  # separately controlled observers
        for field in ('fault','input_delivered'):
            changed = copy.deepcopy(rows)
            changed[0][field] = 1 if field == 'fault' else []
            with self.assertRaises(ValueError):
                equivalent(receipt,changed,receipt,changed,True)

    def test_overwritten_camera_is_retained_not_relabelled_as_the_store(self):
        ram = bytearray(2048)
        ram[0xf6] = 42
        row = dict(game_ram_hex=ram.hex(),phase='room_entry')
        commit = dict(frame=1,line=12,camera=42)
        intervals = [dict(commit=commit)]
        self.assertEqual(store_mismatches(intervals,[row]), [])
        ram[0x3d] = 1
        row['game_ram_hex'] = ram.hex()
        failures = store_mismatches(intervals,[row])
        self.assertEqual(failures,[dict(commit=commit,frame_end_camera=298,phase='room_entry')])
        self.assertEqual(commit['camera'],42)
        row['game_ram_hex'] = '00'
        with self.assertRaises(ValueError):
            store_mismatches(intervals,[row])
