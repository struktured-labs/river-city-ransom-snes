from pathlib import Path
import unittest

from tools.build_ring_stride_trial import patch,HELPER,PREFIX
from tools.check_ring_stride import independent


class RingStrideTests(unittest.TestCase):
    def fixture(self):
        image=bytearray(b'\xff'*0x200000)
        for bank in range(1,9):image[bank*65536+0x3042:bank*65536+0x3047]=PREFIX
        return image,b'\x08'+b'\xea'*255

    def test_patch_scope_and_repeat_rejection(self):
        image,helper=self.fixture();new=patch(image,helper,0x3042)
        allowed=set(range(0xffdc,0xffe0))
        for bank in range(1,9):
            base=bank*65536
            allowed.update(range(base+0x3042,base+0x3047));allowed.update(range(base+HELPER,base+HELPER+256))
            self.assertEqual(new[base+0x3042:base+0x3047],b'\x4c'+HELPER.to_bytes(2,'little')+b'\xea\xea')
        self.assertTrue(all(i in allowed for i,(a,b) in enumerate(zip(image,new)) if a!=b))
        with self.assertRaises(ValueError):patch(new,helper,0x3042)

    def test_wrong_preimage_and_occupied_space_rejected(self):
        for case in ('preimage','occupied','short'):
            image,helper=self.fixture()
            if case=='preimage':image[0x83042]=0
            elif case=='occupied':image[0x76900]=0
            else:helper=helper[:-1]
            with self.assertRaises(ValueError):patch(image,helper,0x3042)

    def test_independent_unchanged_boundary_and_mutation(self):
        case=dict(PPUADDR=0x23ff,COUNT=2,RINGINDEX=63,MIRROR=1,STRIDE=4,UNCHANGED=1,FLAGS=0x35,BANK=0xc1)
        ram=bytearray(131072);ram[0x1d00:0x1d80]=bytes(i&3 for i in range(128))
        ram[0x1c26:0x1c28]=(0x243f).to_bytes(2,'little');ram[0x1c09]=0xfe
        ram[0x6000]=1;ram[0x6003:0x6009]=bytes((1,0,0x34,0x12,0x82,0xff))
        self.assertTrue(independent(ram,case))
        for address in (0x12000,0x1d00,0x1c26,0x1c09,0x6003):
            changed=bytearray(ram);changed[address]^=1
            with self.assertRaises(ValueError,msg=hex(address)):independent(changed,case)

    def test_unsupported_oracle_cases_are_not_claimed_independent(self):
        case=dict(PPUADDR=0x3f10,COUNT=20,FLAGS=0x35)
        self.assertFalse(independent(bytearray(131072),case))
        self.assertFalse(independent(bytearray(131072),dict(case,PPUADDR=0x2000,FLAGS=0x3d)))
        self.assertFalse(independent(bytearray(131072),dict(case,PPUADDR=0x2000,COUNT=0)))
