import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.audit_late_scroll_lines import audit


class LateScrollLinesTests(unittest.TestCase):
    def test_requires_original_failure_and_bound_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root/'report.json'
            report.write_text(json.dumps(dict(late_publications=[])))
            with self.assertRaisesRegex(ValueError, 'original late'):
                audit(root, root, root, root, root/'out')
            report.write_text(json.dumps(dict(late_publications=[dict(frame=5)],
                sources=dict(snes=dict(capture_sha256='other')))))
            with patch('tools.audit_late_scroll_lines.sha', return_value='current'):
                with self.assertRaisesRegex(ValueError, 'different capture'):
                    audit(root, root, root, root, root/'out')

    def test_changed_observed_game_state_is_not_excused_as_background_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'report.json').write_text(json.dumps(dict(late_publications=[dict(frame=5)],
                sources=dict(snes=dict(capture_sha256='current')))))
            receipt = dict(system='snes', capture_complete=True, rom_sha256='rom',
                           scenario_sha256='scenario', audio_sha256='audio', frames=1)
            baseline = (receipt, [dict(frame=1, game_ram_hex='00')])
            changed = (receipt, [dict(frame=1, game_ram_hex='01', background={})])
            with patch('tools.audit_late_scroll_lines.sha', return_value='current'), \
                 patch('tools.audit_late_scroll_lines.verify_capture', side_effect=[baseline,changed]):
                with self.assertRaisesRegex(ValueError, 'Observer changed'):
                    audit(root, root/'background', root/'normal', root/'renderer', root/'out')
