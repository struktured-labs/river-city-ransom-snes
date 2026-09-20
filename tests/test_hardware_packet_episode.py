import unittest

from tests.test_audio_packet_log import fixture
from tools.audit_hardware_packet_episode import episode


class HardwarePacketEpisodeTests(unittest.TestCase):
    def test_complete_new_records_across_ring_wrap(self):
        result = episode(fixture(3205), fixture(4443), fixture(4443))
        self.assertEqual(result['episode_records'], 1238)
        self.assertEqual(result['shared_records'], 2857)
        self.assertEqual(result['after_overwritten'], 348)
        self.assertEqual(result['nmi_intervals'], {1: 1237})

    def test_repeat_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, 're-export'):
            episode(fixture(5), fixture(8), fixture(9))

    def test_no_new_or_overwritten_episode_rejected(self):
        for before, after in ((5, 5), (5, 4), (5, 9000)):
            with self.subTest(before=before, after=after), self.assertRaises(ValueError):
                episode(fixture(before), fixture(after), fixture(after))

    def test_changed_shared_history_even_with_valid_checksum_rejected(self):
        changed = fixture(8)
        changed[39] ^= 1
        changed[62] ^= 1
        with self.assertRaisesRegex(ValueError, 'shared'):
            episode(fixture(5), changed, changed)

    def test_timeout_and_nmi_gap_are_retained_as_evidence(self):
        changed = fixture(8)
        # Change the final record's NMI from 7 to 9 and set timeout, repairing XOR.
        at = 8 * 32
        changed[at + 4] = 9
        changed[at + 6] = 1
        changed[at + 30] = 0
        for value in changed[at:at + 30]:
            changed[at + 30] ^= value
        result = episode(fixture(5), changed, changed)
        self.assertEqual(result['timeouts'], 1)
        self.assertEqual(result['nmi_intervals'], {1: 1, 3: 1})
        self.assertEqual(result['irregular_nmi_intervals'][0]['sequence'], 7)


if __name__ == '__main__':
    unittest.main()
