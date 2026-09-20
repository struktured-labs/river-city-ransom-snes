import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from tools.review_sub_wub_hardware import analyze


class SubWubHardwareTests(unittest.TestCase):
    def test_reject_wrong_native_format(self):
        with self.assertRaises(ValueError):
            analyze(np.zeros((240000,2), dtype=np.int16), 44100, Path('unused'))
        with self.assertRaises(ValueError):
            analyze(np.zeros((240000,2)), 48000, Path('unused'))

    def test_glide_failure_not_hidden_by_passing_tail(self):
        pcm = np.zeros((1200000,2), dtype=np.int16)
        with patch('tools.review_sub_wub_hardware.physical_onset',return_value=3), \
             patch('tools.review_sub_wub_hardware.measure',return_value={'gates':{'tail':True}}), \
             patch('tools.review_sub_wub_hardware.curve_hz',return_value=[55]*240), \
             patch('tools.review_sub_wub_hardware.fundamental',return_value=110), \
             patch('tools.review_sub_wub_hardware.frequency',return_value=55):
            result = analyze(pcm,48000,Path('unused'))
        self.assertTrue(result['tail_passed'])
        self.assertFalse(result['passed'])
        self.assertEqual(len(result['notes']),12)
        self.assertEqual(result['notes'][0]['broad_error_percent'],100)
