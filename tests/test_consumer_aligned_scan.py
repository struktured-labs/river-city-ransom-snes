"""Odd-start alignment and complete-ring queue ordering for emitted code."""
import random
import unittest
from tests.test_consumer_linear_scan import ConsumerLinearTests,execute
from tools.consumer_aligned_scan import assemble


def search(code,x,y,flags):
    for _ in range(260):
        x,y,target,wide,_=execute(code,x,y,flags)
        if target==0x844f:return x,y,False
        if target==0x839e:continue
        if target==0x83a3 and x<=120 and y>=8 and not any(v&2 for v in flags[x:x+8]):
            x=(x+8)%128;y-=8
        elif target in (0x83a3,0x83d9):
            if flags[x]&2:return x,y,True
            x=(x+1)%128;y-=1
        else:raise AssertionError('Unexpected target')
        if not y:return x,0,False
    raise AssertionError('Unbounded search')


class ConsumerAlignedTests(ConsumerLinearTests):
    @classmethod
    def setUpClass(cls):cls.code=assemble()

    def test_all_empty_ring_budget_boundaries(self):
        for x in range(128):
            for y in range(1,129):
                result=execute(self.code,x,y,bytes([1]*128),wide=bool(y&1))
                if x%2:expected=(x,y,0x83d9,False)
                elif x+y<128:expected=(x,y,0x83a3,False)
                else:
                    remaining=y-(128-x)
                    expected=(0,remaining,0x839e if remaining else 0x844f,True)
                self.assertEqual(result[:4],expected)

    def test_complete_search_matches_scalar_queue_for_sparse_and_dense_flags(self):
        rng=random.Random(3569)
        for density in (0,0.015,0.1,0.5,1):
            for _ in range(500):
                flags=bytes(rng.choice((2,3)) if rng.random()<density else rng.choice((0,1)) for _ in range(128))
                x=rng.randrange(128);y=rng.randrange(1,129)
                offset=next((n for n in range(y) if flags[(x+n)%128]&2),None)
                expected=((x+y)%128,0,False) if offset is None else ((x+offset)%128,y-offset,True)
                self.assertEqual(search(self.code,x,y,flags),expected)


if __name__=='__main__':unittest.main()
