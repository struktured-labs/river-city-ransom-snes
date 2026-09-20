import unittest

from tools.check_second_tick_prepare import STABLE, expected


class SecondTickPrepareTests(unittest.TestCase):
    def test_schedule_service_and_rollover(self):
        self.assertEqual(expected(STABLE,0,0,0), (bytes.fromhex('01010000000000'),0))
        self.assertEqual(expected(STABLE,0,0,1), (bytes.fromhex('00010001000000'),1))
        self.assertEqual(expected(STABLE,0,65535,2), (bytes(7),1))
        self.assertEqual(expected(STABLE,0,0,3), (bytes(7),0))

    def test_pause_and_existing_pending_do_not_reschedule(self):
        state=list(STABLE);state[2]=0x20
        self.assertEqual(expected(state,0,0,0), (bytes(7),1))
        self.assertEqual(expected(STABLE,1,0,0), (bytes.fromhex('01000000000000'),1))
        self.assertEqual(expected(STABLE,1,0,4), (bytes.fromhex('00000001000100'),1))
