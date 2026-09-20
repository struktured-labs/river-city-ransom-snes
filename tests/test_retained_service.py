import unittest
from tools.audit_retained_service import identity_gates


class RetainedServiceTests(unittest.TestCase):
    def test_seven_packets_cannot_hide_one_missing_body(self):
        wanted=list(range(1860,1867))
        gates,_=identity_gates(1859,1866,wanted[1:],wanted)
        self.assertFalse(gates['original_bodies_once_in_order'])
        self.assertTrue(gates['sound_packets_once_in_order'])
        self.assertTrue(all(identity_gates(1859,1866,wanted,wanted)[0].values()))

    def test_duplicate_or_reordered_sound_is_rejected(self):
        bodies=[65535,0,1]
        self.assertTrue(all(identity_gates(65534,1,bodies,bodies)[0].values()))
        for packets in ([65535,0,0,1],[65535,1,0],[]):
            self.assertFalse(identity_gates(65534,1,bodies,packets)[0]['sound_packets_once_in_order'])


if __name__=='__main__':unittest.main()
