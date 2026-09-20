import unittest

from tools.camera_state_log import decode,seed_bytes


class CameraStateLogTests(unittest.TestCase):
    def test_empty_seed_and_wrong_schema(self):
        self.assertEqual(decode(seed_bytes())['total'],0)
        wrong=bytearray(seed_bytes());wrong[:8]=b'RCRLOG01'
        with self.assertRaises(ValueError):decode(wrong)

    def test_record_fields_and_corruption(self):
        data=bytearray(seed_bytes());data[8:12]=(1).to_bytes(4,'little');data[12:14]=(0x6040).to_bytes(2,'little')
        r=bytearray(32);r[4:6]=(123).to_bytes(2,'little')
        r[7:11]=bytes((45,1,46,1));r[11:15]=bytes((44,1,44,1))
        r[27:29]=(123).to_bytes(2,'little')
        for b in r[:30]:r[30]^=b
        r[31]=0xA5;data[32:64]=r
        record=decode(data)['records'][0]
        self.assertEqual(record['working_camera'],301)
        self.assertEqual(record['committed_camera'],302)
        self.assertEqual(record['display_camera'],300)
        self.assertFalse(record['nmi_changed_during_record'])
        data[32+10]^=1
        with self.assertRaises(ValueError):decode(data)
