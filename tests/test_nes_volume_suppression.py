import unittest

from tools.plan_nes_volume_suppression import select
from tools.build_nes_volume_suppression_core import transform
from tools.capture_nes_volume_sensitivity import nonaudio,validate_log


def write(clock,value,register=4):
    return dict(frame=1,clock=clock,pc=0x7f8,register=register,value=value)


class NESVolumeSuppression(unittest.TestCase):
    def test_complete_duplicate_zero_run_and_final_write_retained(self):
        ws=[write(5,0xf3),write(12,0xf0),write(14,0xf0),write(20,0xf2),write(22,1,7)]
        pairs=[dict(entry=dict(clock=10),returned=dict(clock=30))]
        cases,excluded,drops=select(ws,pairs)
        self.assertEqual([w['clock'] for w in drops],[12,14])
        self.assertEqual(cases[0]['duration_cycles'],8)
        self.assertEqual(cases[0]['final']['value'],0xf2)
        self.assertFalse(excluded)

    def test_mode_changes_unknown_prior_and_already_quiet_rejected(self):
        pairs=[dict(entry=dict(clock=10),returned=dict(clock=30))]
        for ws in ([write(12,0xf0),write(20,0xf3)],
                   [write(5,0xf0),write(12,0xf0),write(20,0xf3)],
                   [write(5,0xb3),write(12,0xf0),write(20,0xf3)],
                   [write(5,0xf3),write(12,0xf0),write(20,0xb3)],
                   [write(5,0xf3),write(12,0xf0),write(31,0xf3)]):
            with self.assertRaises(ValueError):select(ws,pairs)

    def test_hook_requires_exact_existing_observer(self):
        old='static INLINE void WrMemNorm(uint32_t A, uint8_t V) {\n    rcr_scroll_write(A, V);\n    #include "../../../tools/fceumm_apu_write_clock.inc"\n\tBWrite[A](A, V);\n}'
        changed=transform(old)
        self.assertIn('if (!rcr_suppress_apu_write(A,V)) BWrite[A](A,V);',changed)
        self.assertIn('fceumm_apu_write_clock.inc',changed)
        for wrong in ('',old+old):
            with self.assertRaises(ValueError):transform(wrong)

    def test_executed_schedule_requires_exact_identity_and_completion(self):
        drops=[write(12,0xf0)]
        rows=[['D','1','12','07f8','4004','240'],['E','1']]
        self.assertEqual(validate_log(rows,drops),1)
        for bad in (rows[:1],[rows[0],['E','2']],
                    [['D','1','13','07f8','4004','240'],rows[1]]):
            with self.assertRaises(ValueError):validate_log(bad,drops)

    def test_comparison_keeps_sample_count_and_original_state(self):
        a=[dict(frame=1,audio_start_sample=0,game_ram_hex='0000',audio=dict(samples=800,peak=10,rms=2,ac_rms=1))]
        b=[dict(a[0],audio=dict(samples=800,peak=11,rms=3,ac_rms=2))]
        self.assertEqual(nonaudio(a),nonaudio(b))
        b[0]['audio']['samples']=799
        self.assertNotEqual(nonaudio(a),nonaudio(b))


if __name__=='__main__':unittest.main()
