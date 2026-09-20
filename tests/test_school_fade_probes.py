import unittest

from tools.build_hidden_cap_probe import patch as cap_patch
from tools.build_render_edge_prepare import patch as edge_patch,PATTERN,HELPER


class SchoolFadeProbeTests(unittest.TestCase):
    def cap_image(self):
        image=bytearray(b'\xff'*2097152)
        code=bytes.fromhex('a900cde11ca910e9004c6a88')
        image[0xaa88:0xaa88+len(code)]=code
        return image

    def test_cap_only_changes_budget_and_checksum(self):
        image=self.cap_image()
        for budget in (2,8,12,16):
            result=cap_patch(image,0xaa88,budget)
            self.assertEqual(result[0xaa8e],budget)
            self.assertTrue(all(i==0xaa8e or 0xffdc<=i<0xffe0 for i,(a,b) in enumerate(zip(image,result)) if a!=b))

    def test_cap_bounds_and_preimage(self):
        for budget in (True,0,1,17,12.0):
            with self.assertRaises(ValueError):cap_patch(self.cap_image(),0xaa88,budget)
        image=self.cap_image();image[0xaa88]=0
        with self.assertRaises(ValueError):cap_patch(image,0xaa88,12)

    def edge_image(self):
        image=bytearray(b'\xff'*2097152)
        for bank in range(1,9):
            start=bank*65536+0x282a
            image[start:start+len(PATTERN)]=PATTERN
        helper=bytes.fromhex('8da01c0848')+b'\xff'*59
        return image,helper

    def test_edge_scope_all_banks_and_preserve_shift_gap(self):
        image,helper=self.edge_image();result,sites=edge_patch(image,helper)
        allowed=set(range(0xffdc,0xffe0))
        self.assertEqual(len(sites),8)
        for site in sites:
            base=site['bank']*65536
            self.assertEqual(result[base+site['site']:base+site['site']+3],bytes.fromhex('20807f'))
            self.assertEqual(result[base+HELPER:base+HELPER+64],helper)
            self.assertEqual(result[base+0x7fc0:base+0x8000],image[base+0x7fc0:base+0x8000])
            allowed.update(range(base+site['site'],base+site['site']+3));allowed.update(range(base+HELPER,base+HELPER+64))
        self.assertTrue(all(i in allowed for i,(a,b) in enumerate(zip(image,result)) if a!=b))
        with self.assertRaises(ValueError):edge_patch(result,helper)

    def test_edge_occupied_gap_and_missing_bank_refused(self):
        image,helper=self.edge_image();image[3*65536+HELPER]=0
        with self.assertRaises(ValueError):edge_patch(image,helper)
        image,helper=self.edge_image();image[8*65536+0x282a]=0
        with self.assertRaises(ValueError):edge_patch(image,helper)

    def test_edge_duplicate_pattern_and_bad_helper_refused(self):
        image,helper=self.edge_image();image[0x12a00:0x12a00+len(PATTERN)]=PATTERN
        with self.assertRaises(ValueError):edge_patch(image,helper)
        image,helper=self.edge_image()
        for changed in (helper[:-1],b'\x00'*64):
            with self.assertRaises(ValueError):edge_patch(image,changed)
