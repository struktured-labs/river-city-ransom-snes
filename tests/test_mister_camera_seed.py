import copy
import unittest
from tools.stage_mister_camera_seed import validate_boundary


class CameraSeedBoundaryTests(unittest.TestCase):
    def proof(self):
        return dict(passed=True,quick=False,cutoff=230,cases=[dict(passed=True) for _ in range(168)],
            mutants=[dict(mutant=n,passed=False) for n in
                     ('late-record','native-interrupt','wrong-wrap-bank','wrong-commit')])

    def test_current_boundary_and_wrong_policy(self):
        validate_boundary(self.proof(),230)
        with self.assertRaises(ValueError):validate_boundary(self.proof(),194)

    def test_false_green_summary_and_missing_cases_rejected(self):
        for alter in (lambda p:p['cases'][0].update(passed=False),
                      lambda p:p['cases'].pop(),lambda p:p.update(quick=True)):
            p=self.proof();alter(p)
            with self.assertRaises(ValueError):validate_boundary(p,230)

    def test_missing_duplicate_or_surviving_mutants_rejected(self):
        for alter in (lambda p:p['mutants'].pop(),
                      lambda p:p['mutants'].__setitem__(0,copy.deepcopy(p['mutants'][1])),
                      lambda p:p['mutants'][0].update(passed=True)):
            p=self.proof();alter(p)
            with self.assertRaises(ValueError):validate_boundary(p,230)
