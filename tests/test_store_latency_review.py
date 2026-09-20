import hashlib
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from tools.benchmark_report import sha
from tools.build_store_latency_review import frame_panel


class StoreLatencyReviewTests(unittest.TestCase):
    def fixture(self,root):
        image=Image.new('RGB',(8,8),(16,32,48));path=root/'frame.png';image.save(path)
        return dict(frame_image=path.name,frame_image_sha256=sha(path),
                    video_sha256=hashlib.sha256(image.tobytes()).hexdigest())

    def test_exact_original_frame_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);row=self.fixture(root)
            self.assertEqual(frame_panel(root,row),root/'frame.png')

    def test_changed_png_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);row=self.fixture(root);row['frame_image_sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'source PNG'):frame_panel(root,row)

    def test_rehashed_but_different_video_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);row=self.fixture(root);row['video_sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'captured video'):frame_panel(root,row)
