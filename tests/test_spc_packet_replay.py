import unittest
import numpy as np
from tools.audit_spc_packet_replay import validate
from tools.audit_packet_player_video import decode_marker
from tools.replay_spc_packets import packets
from tools.benchmark_capture import scenario_for, SCENARIO


class PacketReplayTests(unittest.TestCase):
    def packet(self,frame=2):
        return [['P',str(frame),'0','0','0',str(i),str(i),'000000'] for i in range(23)]

    def test_empty_frames_and_packet_order_retained(self):
        grouped,payload=packets(self.packet(),4)
        self.assertEqual(grouped,[[],[bytes(range(23))],[],[]])
        self.assertEqual(payload,b'\0\1'+bytes(range(23))+b'\0\0')

    def test_reject_missing_reordered_duplicate_and_wrong_value(self):
        bad_value=self.packet();bad_value[5][6]='256'
        for rows in ([],self.packet()[:-1],self.packet()[1:],list(reversed(self.packet())),
                     self.packet()+self.packet(),bad_value):
            with self.assertRaises(ValueError):packets(rows,4)

    def test_reject_interleaved_write_and_out_of_window(self):
        rows=self.packet();rows.insert(3,['W','2','0','0','0','1','10','000000'])
        for data in (rows,self.packet(5)):
            with self.assertRaises(ValueError):packets(data,4)

    def test_scenario_starts_from_recognized_street_and_no_memory_mutation(self):
        s=scenario_for('combat-knockdown-audio')
        split=next(i for i,p in enumerate(SCENARIO) if p['name']=='idle')
        self.assertEqual(s[:split],SCENARIO[:split])
        self.assertTrue(any(p.get('until')=='street' for p in s[:split]))
        self.assertEqual(next(p for p in s if p['name']=='combat_take_hits'),
                         dict(name='combat_take_hits',frames=720))
        self.assertTrue(all(set(p)<= {'name','frames','buttons','pulse'} for p in s[split:]))


class ReceiverTests(unittest.TestCase):
    def test_actual_receiver_checks_bytes_order_length_and_pc(self):
        payload = b'\0\1'+bytes(range(23))+b'\0'
        pcs = (0x32e5, 0x32f1)
        rows = [[str(i),str(i),hex(pcs[i%2])] for i in range(23)]
        self.assertTrue(validate(rows,payload,pcs)['passed'])
        for field, value in ((0,'9'),(1,'42'),(2,'0x3000')):
            broken = [r.copy() for r in rows];broken[3][field] = value
            self.assertFalse(validate(broken,payload,pcs)['passed'])
        for broken in (rows[:-1],rows+rows[:1],list(reversed(rows)),[]):
            self.assertFalse(validate(broken,payload,pcs)['passed'])

    def test_malformed_stream_and_trace_rejected(self):
        for payload in (b'\2',b'\1'+bytes(22)):
            with self.assertRaises(ValueError):validate([],payload,(1,2))
        with self.assertRaises(ValueError):validate([['1','2']],b'\1'+bytes(23),(1,2))


class MarkerTests(unittest.TestCase):
    def marker(self, value):
        rgb = np.zeros((239,256,3),dtype=np.uint8)
        for i in range(16):
            bit = (value>>i)&1
            rgb[39:47,64+8*i:72+8*i] = bit*255
            rgb[47:55,64+8*i:72+8*i] = (1-bit)*255
        return rgb

    def test_all_bit_positions_and_extremes(self):
        for value in [0,65535,2906]+[1<<i for i in range(16)]:
            self.assertEqual(decode_marker(self.marker(value)),value)

    def test_blank_corrupt_ambiguous_and_wrong_bounds(self):
        image = self.marker(2906)
        for value in (0,128):
            bad = image.copy();bad[47:55,64:72] = value
            with self.assertRaises(ValueError):decode_marker(bad)
        with self.assertRaises(ValueError):decode_marker(np.zeros_like(image))
        with self.assertRaises(ValueError):decode_marker(image,(64,39,256,16))
