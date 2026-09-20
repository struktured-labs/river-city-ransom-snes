from pathlib import Path
import unittest
from unittest.mock import patch

from tools.audit_noise_reference_filter import validate_controls


class NoiseReferenceFilterTests(unittest.TestCase):
    def receipts(self):
        return [dict(passed=True,sources={'core.so':'abc'}),
            dict(observer_neutral=True,sources={'core.so':'abc','normal/report.json':'abc'})]

    def test_same_core_provenance_is_required_even_for_equal_pcm(self):
        for changed in (False,True):
            receipts=self.receipts()
            if changed:receipts[0]['sources']={'other-core.so':'abc'}
            with patch('tools.audit_noise_reference_filter.bound_report',side_effect=receipts), \
                 patch('tools.audit_noise_reference_filter.sha',return_value='abc'):
                if changed:
                    with self.assertRaises(ValueError):
                        validate_controls(Path('normal'),Path('capture'),Path('core.so'))
                else:validate_controls(Path('normal'),Path('capture'),Path('core.so'))

    def test_changed_observer_pcm_rejected(self):
        def digest(path):
            return 'changed' if path==Path('capture/audio.wav') else 'abc'
        with patch('tools.audit_noise_reference_filter.bound_report',side_effect=self.receipts()), \
             patch('tools.audit_noise_reference_filter.sha',side_effect=digest):
            with self.assertRaises(ValueError):
                validate_controls(Path('normal'),Path('capture'),Path('core.so'))
