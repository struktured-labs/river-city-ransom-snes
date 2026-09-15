import unittest

from tools.profile_native import nmi_stalls


class NmiStallTests(unittest.TestCase):
    def rows(self, counters):
        return [{'frame': i + 1, 'nmi': count, 'pc': None}
                for i, count in enumerate(counters)]

    def test_resumed_and_unfinished_runs(self):
        rows = self.rows([3, 3, 3, 4, 5, 5])
        self.assertEqual(nmi_stalls(rows), [
            {'before': rows[0], 'samples': rows[1:3], 'after': rows[3]},
            {'before': rows[4], 'samples': rows[5:], 'after': None},
        ])

    def test_no_stall_or_insufficient_samples(self):
        for counters in ([], [1], [1, 2, 3], [65535, 0, 1]):
            self.assertEqual(nmi_stalls(self.rows(counters)), [])
