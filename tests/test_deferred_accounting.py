import unittest
from tools.audit_deferred_accounting import analyze


def row(frame, scheduled, served, pending=0, fallback=0):
    return dict(frame=frame, native=dict(deferred_game_nmi_scheduled=scheduled,
        deferred_game_nmi_served=served, deferred_game_nmi_pending=pending,
        deferred_game_nmi_fallback=fallback))


class DeferredAccountingTests(unittest.TestCase):
    def test_complete_job_and_counter_wrap(self):
        result = analyze([row(1, 65535, 65535), row(2, 0, 65535, 1), row(3, 0, 0)])
        self.assertEqual(result['scheduled_advances'], 1)
        self.assertEqual(result['served_advances'], 1)

    def test_lost_duplicate_and_pending_jobs_fail(self):
        for bad in (row(2, 1, 0), row(2, 0, 1), row(2, 2, 2),
                    row(2, 1, 0, 1), row(2, 1, 1, fallback=1)):
            with self.assertRaises(ValueError):analyze([row(1, 0, 0), bad])

    def test_missing_frames_or_activity_rejected(self):
        for timeline in ([], [row(1, 0, 0), row(2, 0, 0)],
                         [row(1, 0, 0), row(3, 1, 1)]):
            with self.assertRaises(ValueError):analyze(timeline)
