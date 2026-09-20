import unittest
from pathlib import Path
from tools.build_timed_receiver_fixture import stage
from tools.check_timed_receiver import deadline_bounds


class TimedReceiver(unittest.TestCase):
    def test_footprint(self):
        original=Path('build/early-oam-live-half-game-3955/native-cpu.sfc').read_bytes()[0x120000:0x123140]
        image,labels=stage(original)
        allowed={i for pc in (0x487,0x3279,0x3296) for i in range(pc-0x400,pc-0x400+3)}
        self.assertTrue(all(a==b or i in allowed for i,(a,b) in enumerate(zip(original,image))))
        self.assertTrue(0x3540<=labels['arm']<labels['commit']<0x3600)
        self.assertEqual(labels['advance_wrapper'],0x3640)
        self.assertEqual(image[0x3600-0x400:0x3640-0x400],bytes(64))
        with self.assertRaises(ValueError):stage(image)

    def test_deadline_window(self):
        self.assertEqual(deadline_bounds(1000,2000,8),(4584,6496))
        self.assertEqual(deadline_bounds(1000,9000,8),(9000,10400))
        self.assertEqual(deadline_bounds(1000,2000,0),(2000,3400))
        self.assertEqual(deadline_bounds(1000,2000,255),deadline_bounds(1000,2000,32))
