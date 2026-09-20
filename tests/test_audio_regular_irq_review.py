import unittest
from tools.review_audio_regular_irq import events


class Events(unittest.TestCase):
    def rows(self):
        return [[str(f), '80', '100', str(f*100+i), pc] for f in range(8530, 8534)
                for i, pc in enumerate(('c1fa54', 'c7fa64'))]

    def test_complete_and_missing(self):
        self.assertEqual(len(events(self.rows())), 8)
        for i in range(8):
            rows = self.rows()
            del rows[i]
            with self.assertRaises(ValueError):
                events(rows)

    def test_nonmonotonic(self):
        with self.assertRaises(ValueError):
            events(list(reversed(self.rows())))
