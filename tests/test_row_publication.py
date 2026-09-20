import unittest
from tools.review_row_publication import generations, health_gate


def sample(frame, shadow, staged, vram):
    return dict(frame=frame, rows={'2': dict(shadow=bytes([shadow]).hex(),
        staged=bytes([staged, 8]).hex(), vram=bytes([vram, 8]).hex())})


class PublicationTests(unittest.TestCase):
    def test_measures_actual_chain(self):
        rows = [sample(1,1,1,1), sample(2,2,1,1), sample(3,2,2,1), sample(4,2,2,2)]
        e, = generations(rows, 2)
        self.assertEqual((e['source_frame'],e['staged_latency'],e['vram_latency']), (2,1,2))
        self.assertTrue(health_gate(e, 2))
        self.assertFalse(health_gate(e, 1))

    def test_superseded_generation_is_not_dropped(self):
        rows = [sample(1,1,1,1), sample(2,2,1,1), sample(3,3,3,3)]
        e, last = generations(rows, 2)
        self.assertEqual(e['status'], 'superseded_without_publication')
        self.assertFalse(health_gate(e, 10))
        self.assertEqual(last['vram_latency'], 0)

    def test_gaps_and_right_censoring_are_not_false_publication(self):
        rows = [sample(1,1,1,1), sample(2,2,2,1), sample(8,2,2,2)]
        e, = generations(rows, 2)
        self.assertEqual(e['status'], 'right_censored')
        self.assertIsNone(e['vram_latency'])
        self.assertFalse(health_gate(e, 100))


if __name__ == '__main__':
    unittest.main()
