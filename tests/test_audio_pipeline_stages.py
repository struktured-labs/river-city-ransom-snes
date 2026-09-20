import unittest

from tools.audit_audio_pipeline import stages, intervals


def event(kind, clock, pc='c1fa54', native=1):
    return list(map(str, (kind, 1, 250, 0, clock, pc, native, 192, 0, 0, 0, 0, 1, 0, 0, 128)))


def packet(start=100, native=1):
    return [event(7,start,native=native),event(0,start+10,native=native),event(1,start+20,native=native),
            event(2,start+30,'c081ba',native),event(3,start+40,'c0d2bc',native)]+[
            event(4,start+50+i,'c0d2d0',native) for i in range(12)]+[
            event(5,start+70,'c0d2f5',native),event(6,start+80,'c081fd',native)]


class AudioPipelineStageTests(unittest.TestCase):
    def test_complete_packet_and_exact_signed_decomposition(self):
        decoded=stages(packet()+packet(1000,2))
        measured,excluded=intervals(decoded,{2})
        self.assertEqual(len(measured),1);self.assertEqual(excluded,[])
        self.assertEqual(measured[0]['completion_gap'],900)
        self.assertEqual(measured[0]['entry_gap'],900)
        self.assertEqual(sum(measured[0]['stage_changes'].values()),0)

    def test_missing_return_wrong_owner_and_byte_count_fail(self):
        for index in (2,5):
            bad=packet();bad.pop(index)
            with self.assertRaises(ValueError):stages(bad)
        bad=packet();bad[4][6]='2'
        with self.assertRaises(ValueError):stages(bad)

    def test_driverless_packet_retained_not_invented(self):
        decoded=stages(packet()[3:])
        self.assertIsNone(decoded[0]['driver'])
        with self.assertRaises(ValueError):intervals(decoded,set())

    def test_nonmonotonic_clock_and_false_bank_rejected(self):
        bad=packet();bad[2][4]=bad[1][4]
        with self.assertRaises(ValueError):stages(bad)
        bad=packet();bad[1][5]='c0fa54'
        with self.assertRaises(ValueError):stages(bad)


if __name__ == '__main__':unittest.main()
