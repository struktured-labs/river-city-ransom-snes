import unittest
from tools.check_alias_words import expected


class AliasWordOracleTests(unittest.TestCase):
    def test_unqueued_dirty_alias_only_and_both_directions(self):
        original=bytearray((i^(i>>8))&255 for i in range(8192))
        for source in range(128):
            for mirror in (0,1):
                target=source^(32 if mirror else 64)
                wanted=original.copy()
                wanted[target*64:(target+1)*64]=original[source*64:(source+1)*64]
                self.assertEqual(expected(source,mirror,1),wanted)
                for state in (0,2,3):self.assertEqual(expected(source,mirror,state),original)
