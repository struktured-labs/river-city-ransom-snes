import tempfile
import unittest
from pathlib import Path
import wave

from tools.review_candidate_combat import native_clip


class NativeClipTests(unittest.TestCase):
    def test_native_samples_and_boundaries(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder)/'source.wav', Path(folder)/'clip.wav'
            pcm = bytes(range(64))
            with wave.open(str(source), 'wb') as wav:
                wav.setparams((2, 2, 32040, 0, 'NONE', 'not compressed'))
                wav.writeframes(pcm)
            result = native_clip(source, target, 3, 11)
            self.assertEqual(result['rate'], 32040)
            with wave.open(str(target), 'rb') as wav:
                self.assertEqual(wav.getnframes(), 8)
                self.assertEqual(wav.readframes(8), pcm[12:44])
            for first, last in ((-1, 3), (0, 17), (5, 5), (9, 2)):
                with self.assertRaises(ValueError):
                    native_clip(source, target, first, last)

    def test_mono_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder)/'mono.wav', Path(folder)/'clip.wav'
            with wave.open(str(source), 'wb') as wav:
                wav.setparams((1, 2, 32040, 0, 'NONE', 'not compressed'))
                wav.writeframes(bytes(16))
            with self.assertRaises(ValueError):
                native_clip(source, target, 0, 2)
            self.assertFalse(target.exists())
