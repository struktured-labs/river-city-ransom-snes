"""Execute word-scan machine code against the scalar circular queue oracle."""
import random
import unittest
from tests.test_consumer_linear_scan import execute
from tests.test_consumer_aligned_scan import search
from tools.consumer_word_scan import assemble


class ConsumerWordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.code=assemble()

    def test_empty_ring_all_cursors_and_budgets(self):
        for x in range(128):
            for y in range(1,129):
                self.assertEqual(search(self.code,x,y,bytes([1]*128)),((x+y)%128,0,False))

    def test_every_single_ready_row_from_every_cursor(self):
        for x in range(128):
            for at in range(128):
                flags=bytearray([1]*128);flags[at]=2+(at%2)
                offset=(at-x)%128
                self.assertEqual(search(self.code,x,128,flags),(at,128-offset,True))

    def test_dense_and_sparse_partial_budget_first_ready(self):
        rng=random.Random(3573)
        for density in (0.01,0.1,0.5,1):
            for _ in range(500):
                flags=bytes(rng.choice((2,3)) if rng.random()<density else rng.choice((0,1)) for _ in range(128))
                x=rng.randrange(128);y=rng.randrange(1,129)
                offset=next((i for i in range(y) if flags[(x+i)%128]&2),None)
                expected=((x+y)%128,0,False) if offset is None else ((x+offset)%128,y-offset,True)
                self.assertEqual(search(self.code,x,y,flags),expected)

    def test_dirty_mask_mutation_is_detected(self):
        bad=self.code.replace(bytes.fromhex('a90202'),bytes.fromhex('a90101'))
        flags=bytearray(128);flags[2]=2
        self.assertNotEqual(search(bad,0,128,flags),search(self.code,0,128,flags))


if __name__=='__main__':unittest.main()
