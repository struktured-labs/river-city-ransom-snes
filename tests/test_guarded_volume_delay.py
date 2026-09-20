from pathlib import Path
import unittest
from tools.build_guarded_volume_delay import delay


class GuardedVolumeDelayTests(unittest.TestCase):
    def test_changes_only_delay(self):
        before=Path('build/interleaved-volume-fixtures-3393/trial/engine.bin').read_bytes()
        after,at=delay(before)
        self.assertEqual([i for i,(a,b) in enumerate(zip(before,after)) if a!=b],[at])
        self.assertEqual((before[at],after[at]),(8,13))

    def test_wrong_engine_rejected(self):
        with self.assertRaises(ValueError):delay(bytes(12608))


if __name__=='__main__':unittest.main()
