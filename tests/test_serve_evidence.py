from pathlib import Path
import tempfile
import unittest
from tools.serve_evidence import permitted


class EvidenceServerTests(unittest.TestCase):
    def test_pages_only_and_no_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'review'
            root.mkdir()
            (root/'index.html').write_text('review')
            (root/'game.sfc').write_bytes(b'ROM')
            (root/'capture.mp4').write_bytes(b'video')
            (Path(tmp)/'outside.json').write_text('{}')
            (root/'escape.json').symlink_to(Path(tmp)/'outside.json')
            self.assertEqual(permitted(root,'/'),root/'index.html')
            self.assertEqual(permitted(root,'/capture.mp4'),root/'capture.mp4')
            self.assertEqual(permitted(root,'/index.html?review=1'),root/'index.html')
            for url in ('/game.sfc','/../outside.json','/%2e%2e/outside.json','/escape.json','/missing.png'):
                self.assertIsNone(permitted(root,url))

    def test_no_directory_listing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(permitted(tmp,'/'))
