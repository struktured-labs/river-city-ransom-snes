import hashlib
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from tools.frame_audit import verify_frame


class FrameAuditTests(unittest.TestCase):
    def test_png_and_raw_pixel_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'frames').mkdir()
            path = root/'frames/frame-00001.png'
            source = Image.new('RGB', (4, 4), 'red')
            source.save(path)
            row = dict(frame=1, frame_image='frames/frame-00001.png',
                       frame_image_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                       video_sha256=hashlib.sha256(source.tobytes()).hexdigest())
            self.assertEqual(verify_frame(root, row), path)
            for change in (dict(video_sha256='wrong'), dict(frame_image_sha256='wrong'),
                           dict(frame_image='../outside.png'), dict(frame=2)):
                with self.assertRaises(ValueError):
                    verify_frame(root, row | change)
