from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import Mock, patch

import numpy as np
from PIL import Image

from tools import capture_guarded_mister_scroll as guard


class ScreenGuardTests(unittest.TestCase):
    def test_identical_frame_and_small_cursor_change_pass(self):
        a = np.zeros(guard.GEOMETRY, dtype=np.uint8); b = a.copy()
        self.assertTrue(guard.compare(a, b)['passed'])
        b[1800:1828, 760:788] = 255
        self.assertTrue(guard.compare(a, b)['passed'])

    def test_osd_and_missing_menu_labels_are_rejected(self):
        a = np.zeros(guard.GEOMETRY, dtype=np.uint8)
        for region in ((slice(499, 1650), slice(1153, 2690)),
                       (slice(1781, 2034), slice(750, 2906))):
            b = a.copy(); b[region] = 100
            self.assertFalse(guard.compare(a, b)['passed'])

    def test_outside_chat_does_not_change_game_check(self):
        a = np.zeros(guard.GEOMETRY, dtype=np.uint8); b = a.copy()
        b[:200, :300] = 255
        self.assertTrue(guard.compare(a, b)['passed'])

    def test_geometry_change_rejected(self):
        with self.assertRaises(ValueError):
            guard.compare(np.zeros(guard.GEOMETRY), np.zeros((1080, 1920, 3)))

    def test_wrong_geometry_leaves_rejection_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); reference = root/'reference.png'
            Image.new('RGB', (1920, 1080)).save(reference)
            def observe(url, host, screenshot):
                Image.new('RGB', (1920, 1080)).save(screenshot)
                return dict(scene='river city ransom', recording_active=False,
                            replay_active=False, blackmagic=dict(mute=False))
            with patch.object(guard, 'read', side_effect=observe):
                with self.assertRaisesRegex(ValueError, 'controller input refused'):
                    guard.check(reference, root/'guard')
            report = json.loads((root/'guard/report.json').read_text())
            self.assertFalse(report['passed'])
            self.assertIn('geometry', report['image_error'])
            self.assertTrue(report['no_controller_input_sent'])

    def test_failed_live_guard_cannot_send_input_and_restores_hook(self):
        sender = Mock()
        with patch.object(guard.coordinator, 'run', sender):
            with patch.object(guard, 'check', side_effect=ValueError('OSD visible')):
                with self.assertRaises(ValueError):
                    with guard.guarded_input(Path('reference'), Path('guard')):
                        guard.coordinator.run('rivalmage', [], Path('input'), pad=True)
            sender.assert_not_called()
            self.assertIs(guard.coordinator.run, sender)

    def test_pass_rechecks_immediately_before_one_input_sequence(self):
        sender = Mock(return_value='sent')
        with patch.object(guard.coordinator, 'run', sender):
            with patch.object(guard, 'check') as checker:
                with guard.guarded_input(Path('reference'), Path('guard')):
                    self.assertEqual(guard.coordinator.run('rivalmage', [], Path('input'), pad=True), 'sent')
                    with self.assertRaises(ValueError):
                        guard.coordinator.run('rivalmage', [], Path('input'), pad=True)
                checker.assert_called_once_with(Path('reference'), Path('guard/at-input'), recording=True)
            sender.assert_called_once()

    def test_initial_failure_does_not_start_recorder(self):
        with patch.object(guard, 'check', side_effect=ValueError('wrong screen')):
            with patch.object(guard, 'scroll') as runner:
                with self.assertRaises(ValueError):
                    guard.capture(Path('r'), Path('/nonexistent-capture-guard-test/a'),
                                  Path('/nonexistent-capture-guard-test/b'), Path('/nonexistent-capture-guard-test/c'))
                runner.assert_not_called()
