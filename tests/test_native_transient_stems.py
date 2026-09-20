import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from tests.test_receiver_dispatch import fixture
from tools.build_dispatch_packet_replay import replace
from tools.build_receiver_dispatch_trial import patch as dispatch_patch
from tools.review_native_transient_stems import composition, mapped_window, steps_at_peak, same_core_load, compare_ready


class DispatchReplayTests(unittest.TestCase):
    def test_exact_existing_engine_change_and_no_other_player_changes(self):
        old, layout, poll = fixture()
        new, _ = dispatch_patch(old,layout,poll)
        image = bytearray(0x200000)
        image[0x120000:0x120000+len(old)] = old
        changed, _ = replace(image,old,new,layout,poll)
        allowed = {0x120105,0x120106,*range(0xffdc,0xffe0)}
        self.assertTrue(all(i in allowed for i,(a,b) in enumerate(zip(image,changed)) if a!=b))
        bad = bytearray(new); bad[0] ^= 1
        with self.assertRaises(ValueError): replace(image,old,bad,layout,poll)
        image[0x120010] ^= 1
        with self.assertRaises(ValueError): replace(image,old,new,layout,poll)


class TransientStemTests(unittest.TestCase):
    def test_ready_equivalence_does_not_hide_different_write_sequences(self):
        ready = {1:dict(registers=[0]*128)}
        a = [dict(packet=1,register=0,value=0)]
        b = [dict(packet=1,register=0,value=1),*a]
        result = compare_ready(a,ready,b,ready)
        self.assertEqual(result['changed_ready_states'],[])
        self.assertEqual(result['changed_write_sequences'][0]['added'],1)
        mutated = {1:dict(registers=[2]+[0]*127)}
        self.assertEqual(compare_ready(a,ready,b,mutated)['changed_ready_states'],
                         [dict(packet=1,registers={'00':[0,2]})])
        with self.assertRaises(ValueError): compare_ready(a,ready,b,{})

    def test_rounding_only_composition_and_one_sample_mutation(self):
        a = np.full((50,2),100,dtype=np.int16)
        b = np.full((50,2),-50,dtype=np.int16)
        full = a+b
        full[::2] += 1
        self.assertEqual(composition(full,a,b)['residual_counts'],{'0':50,'1':50})
        for changed in (a.copy(),a.astype(np.int32),a[:-1],np.zeros_like(a)):
            if changed.shape == a.shape and changed.dtype == a.dtype and np.any(changed):
                changed[10,0] += 4
            with self.assertRaises(ValueError): composition(full,changed,b)

    def test_no_phase_fitting_or_replay_tail_coverage(self):
        timeline = [dict(start_sample=100,end_sample=200),dict(start_sample=200,end_sample=300)]
        good = mapped_window(dict(sample=600),1000,1000,.4,timeline)
        self.assertTrue(good['covered'])
        self.assertAlmostEqual(good['center_seconds'],.2)
        self.assertEqual((good['first'],good['last']),(180,220))
        # Sound may remain in the WAV beyond command coverage: reject it anyway.
        for sample in (490,700,900):
            self.assertFalse(mapped_window(dict(sample=sample),1000,1000,.4,timeline)['covered'])
        for lag in (float('nan'),float('inf')):
            with self.assertRaises(ValueError): mapped_window(dict(sample=600),1000,1000,lag,timeline)

    def test_components_measured_at_same_sample_not_separate_peaks(self):
        noise = np.zeros((20,2),dtype=np.int16)
        rest = noise.copy()
        noise[5:,0] = 1000; rest[5:,0] = -100
        rest[8:,1] = 800
        result = steps_at_peak(dict(replay=noise+rest,noise=noise,rest=rest),1,12)
        self.assertEqual((result['sample'],result['channel']),(5,0))
        parts = result['channels_at_identical_sample']
        self.assertEqual(parts['noise']['signed_step'],1000)
        self.assertEqual(parts['rest']['signed_step'],-100)
        self.assertEqual(parts['rest']['window_max_step'],800)
        self.assertEqual(parts['replay']['signed_step'],900)

    def test_different_core_observer_control_is_rejected(self):
        with patch('tools.review_native_transient_stems.bound_report',side_effect=[
            dict(sources={'a.so':'abc'}),dict(sources={'b.so':'abc'})]), \
                patch('tools.review_native_transient_stems.load') as run:
            with self.assertRaises(ValueError): same_core_load(Path('a'),Path('b'),Path('c'))
            run.assert_not_called()

    def test_same_core_is_required_before_delegated_full_validation(self):
        with patch('tools.review_native_transient_stems.bound_report',return_value=dict(sources={'a.so':'abc'})), \
                patch('tools.review_native_transient_stems.load',return_value='checked') as run:
            self.assertEqual(same_core_load(Path('a'),Path('b'),Path('c')),'checked')
            run.assert_called_once()
