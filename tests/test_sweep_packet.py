import unittest
from tools.build_sweep_packet import metadata,build
from tools.build_sweep_kernel import build as kernel


class SweepPacketTests(unittest.TestCase):
    def test_register_bits_distinct(self):
        self.assertEqual([metadata(0,r,0) for r in (1,5,2,3,6,7)],[1,2,4,8,16,32])

    def test_repeat_write_is_still_an_event(self):
        for value in range(256):self.assertEqual(metadata(0,1,value),1)

    def test_frame_last_mode_preserves_pulse_events(self):
        for previous in range(256):
            self.assertEqual(metadata(previous,23,0),previous&63|64)
            self.assertEqual(metadata(previous,23,128),previous&63|192)

    def test_other_registers_leave_events_unchanged(self):
        for r in (0,4,8,9,10,11,12,13,14,15,16,17,18,19,21):
            self.assertEqual(metadata(0x95,r,123),0x95)

    def test_receiver_explicitly_clears_pending_kon_slot(self):
        code,labels=kernel(0x307f)
        adapter,_=build(0x307f+len(code),labels)
        self.assertEqual(adapter[-4:],bytes.fromhex('8f00546f'))
