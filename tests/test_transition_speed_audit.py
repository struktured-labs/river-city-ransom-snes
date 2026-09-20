import unittest

from tools.audit_transition_speed import evaluate


class TransitionSpeedAuditTests(unittest.TestCase):
    def streams(self):
        common = [0x2301+i for i in range(49)]
        reference = [dict(frame=100+i//2, address=value) for i, value in enumerate(common)]
        candidate = [dict(item) for item in reference]
        reference += [dict(frame=126, address=0x244A),
                      dict(frame=130, address=0x2023),
                      dict(frame=134, address=0x2043)]
        candidate += [dict(frame=126, address=value) for value in (0x2356, 0x2357, 0x2358, 0x2359)]
        candidate += [dict(frame=133, address=0x244A),
                      dict(frame=137, address=0x2023),
                      dict(frame=141, address=0x2043)]
        return reference, candidate

    def test_content_adjusted_cadence_passes(self):
        result = evaluate(*self.streams(), reference_visual_hit=134,
                          candidate_visual_hit=142)
        self.assertTrue(result['passed'])
        self.assertEqual(result['candidate_extra_commands'], ['2356', '2357', '2358', '2359'])
        self.assertEqual(result['target_cadence_frames'], [4, 4])

    def test_slow_target_and_publisher_fail(self):
        reference, candidate = self.streams()
        candidate[-1]['frame'] += 2
        self.assertFalse(evaluate(reference, candidate, 134, 144)['passed'])
        reference, candidate = self.streams()
        self.assertFalse(evaluate(reference, candidate, 134, 144)['passed'])
