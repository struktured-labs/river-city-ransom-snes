import copy
import json
from pathlib import Path
import tempfile
import unittest

from tools.benchmark_report import sha
from tools.build_alley_budget_review import validate_entry


class AlleyBudgetReviewTests(unittest.TestCase):
    def fixture(self, root):
        (root/'capture.json').write_text(json.dumps(dict(rom_sha256='test',capture_complete=True)))
        return dict(passed=False, audit_sha256=sha(Path('tools/audit_room_entry.py')),
                    sources=dict(snes=dict(capture_sha256=sha(root/'capture.json'),rom_sha256='test')),
                    comparisons=[dict(room=i,mismatch_pixels_by_offset=[1]*40) for i in (1,2,3)])

    def test_failed_experiment_is_valid_review_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            report=self.fixture(root)
            validate_entry(report,root)
            self.assertFalse(report['passed'])

    def test_changed_capture_or_incomplete_room_coverage_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            original=self.fixture(root)
            bad=copy.deepcopy(original)
            bad['sources']['snes']['rom_sha256']='different'
            with self.assertRaises(ValueError):
                validate_entry(bad,root)
            bad=copy.deepcopy(original)
            bad['comparisons'][0]['mismatch_pixels_by_offset'].pop()
            with self.assertRaises(ValueError):
                validate_entry(bad,root)
            bad=copy.deepcopy(original)
            bad['comparisons'].pop()
            with self.assertRaises(ValueError):
                validate_entry(bad,root)
