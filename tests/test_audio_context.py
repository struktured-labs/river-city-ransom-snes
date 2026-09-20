import unittest
import numpy as np
from tools.locate_audio_context import rank_matches
from tools.audit_physical_audio_context import fixed_score


class AudioContextTests(unittest.TestCase):
    def fixture(self):
        rng=np.random.default_rng(971)
        reference=rng.random((24,500))
        reference/=np.linalg.norm(reference,axis=0)
        return reference,reference[:,120:170].copy()

    def test_exact_feature_copy_locates_known_position(self):
        reference,query=self.fixture();matches,_=rank_matches(reference,query)
        self.assertEqual(matches[0]['index'],120)
        self.assertAlmostEqual(matches[0]['score'],1)

    def test_repeated_passages_remain_ambiguous_candidates(self):
        reference,query=self.fixture();reference[:,320:370]=query
        matches,_=rank_matches(reference,query)
        self.assertEqual({m['index'] for m in matches[:2]},{120,320})
        self.assertAlmostEqual(matches[0]['score'],matches[1]['score'])

    def test_silent_nonfinite_or_incompatible_query_refused(self):
        reference,query=self.fixture()
        for bad in (query*0,query*np.nan,query[:-1],query[:,:19]):
            with self.assertRaises(ValueError):rank_matches(reference,bad)

    def test_full_context_bound_excludes_late_training_only_match(self):
        reference,query=self.fixture();reference[:,320:370]=query
        matches,_=rank_matches(reference,query,maximum_start=200)
        self.assertTrue(all(m['index']<=200 for m in matches))
        self.assertEqual(matches[0]['index'],120)

    def test_missing_signal_reduces_fixed_position_score(self):
        reference,query=self.fixture();_,baseline=rank_matches(reference,query)
        reference[:,130:150]=0;_,mutant=rank_matches(reference,query)
        self.assertLess(mutant[120],baseline[120]-.3)

    def test_holdout_score_uses_frozen_offset_without_research(self):
        reference,query=self.fixture()
        self.assertAlmostEqual(fixed_score(reference,query,.6,0,.25),1)
        self.assertLess(fixed_score(reference,query,.5,0,.25),.95)
        with self.assertRaises(ValueError):fixed_score(reference,query,3,0,.25)
