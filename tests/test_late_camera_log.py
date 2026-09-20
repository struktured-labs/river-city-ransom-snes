import unittest
from tools.build_late_camera_log import replace_cutoff, patch


class LateCameraLogTests(unittest.TestCase):
    def test_strict_preimage_and_only_operand_changes(self):
        code=bytes.fromhex('ea8ac9c2b003ea')
        self.assertEqual(replace_cutoff(code),bytes.fromhex('ea8ac9e6b003ea'))
        for bad in (b'',code+code,replace_cutoff(code)):
            with self.assertRaises(ValueError):replace_cutoff(bad)
        image=bytearray(b'\xff'*0x200000)
        sites=[bank*65536+0x7b00 for bank in range(1,9)]+[0xe400]
        for start in sites:image[start:start+len(code)]=code
        result=patch(image,code,code)
        changed={i for i,(a,b) in enumerate(zip(image,result)) if a!=b}
        self.assertTrue(changed <= {start+3 for start in sites}|set(range(0xffdc,0xffe0)))
        self.assertTrue({start+3 for start in sites} <= changed)
        with self.assertRaises(ValueError):patch(result,code,code)
