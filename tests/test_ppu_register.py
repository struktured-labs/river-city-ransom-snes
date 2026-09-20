import unittest

from tools.build_ppu_register_trial import patch,HELPER,SIZE,PREFIX
from tools.build_ppu_targeted_trial import patch as targeted
from tools.check_ppu_register import independent


class PpuRegisterTests(unittest.TestCase):
    def fixture(self):
        image = bytearray(b'\xff'*0x200000)
        for bank in range(1,9):
            image[bank*65536+0x2301:bank*65536+0x2301+len(PREFIX)] = PREFIX
        return image,b'\x08'+b'\xea'*(SIZE-1)

    def test_global_patch_scope_and_mirror_preconditions(self):
        image,helper = self.fixture()
        result = patch(image,helper,0x2301)
        allowed = set(range(0xffdc,0xffe0))
        for bank in range(1,9):
            base = bank*65536
            allowed.update(range(base+0x2301,base+0x2304))
            allowed.update(range(base+HELPER,base+HELPER+SIZE))
            for address in (base+0x2308,base+HELPER+SIZE-1):
                wrong = bytearray(image);wrong[address]^=1
                with self.assertRaises(ValueError):patch(wrong,helper,0x2301)
        self.assertTrue(all(i in allowed for i,(a,b) in enumerate(zip(image,result)) if a!=b))
        with self.assertRaises(ValueError):patch(result,helper,0x2301)

    def test_targeted_patch_leaves_generic_and_other_io_alone(self):
        image,helper = self.fixture()
        block = bytes.fromhex('0848220123c1682860')+b'\xea'*7
        for bank in range(1,9):
            for start in (0x6000,0x6010,0x6020):
                image[bank*65536+start:bank*65536+start+16] = block
        meta = dict(stub_bytes=48,patches=[dict(stub=0x6000,opcode=0x8d,operand=0x2006),
            dict(stub=0x6010,opcode=0x8d,operand=0x8000),dict(stub=0x6020,opcode=0x9d,operand=0x2000)])
        result,sites,targets = targeted(image,helper,0x2301,meta)
        self.assertEqual(targets,[0x6000]);self.assertEqual(len(sites),8)
        for bank in range(1,9):
            base = bank*65536
            self.assertEqual(result[base+0x2301:base+0x2309],PREFIX)
            self.assertEqual(result[base+0x6010:base+0x6030],image[base+0x6010:base+0x6030])
        allowed = set(range(0xffdc,0xffe0))|{i for site in sites for i in (site,site+1)}
        for bank in range(1,9):allowed.update(range(bank*65536+HELPER,bank*65536+HELPER+SIZE))
        self.assertTrue(all(i in allowed for i,(a,b) in enumerate(zip(image,result)) if a!=b))
        with self.assertRaises(ValueError):targeted(result,helper,0x2301,meta)
        image[0x76003]^=1
        with self.assertRaises(ValueError):targeted(image,helper,0x2301,meta)

    def test_independent_oracle_checks_unchanged_dirty_and_hidden_b(self):
        case = dict(ADDRESS=0x2000,VALUE=0x18,OLD_CTRL=0x18,LATCH=0,FLAGS=0x35,STACK=255)
        ram = bytearray(131072)
        ram[0x1b00:0x1e00] = b'\x5a'*0x300
        for address,value in ((0x1b20,0),(0x1b21,0x20),(0x1b22,0x18),(0x1c20,0x18),
            (0x1c25,0),(0x1c27,0x20),(0x1c26,0x1f),(0x1c18,0),(0x1c06,0),(0x1c60,1),(0x1c61,0),(0x1c0a,1)):
            ram[address] = value
        ram[0x6000:0x6009] = bytes.fromhex('571b35a659341283ff')
        self.assertTrue(independent(ram,case))
        for address in (0x1cbb,0x1c20,0x1b22,0x6001,0x6002,0x6005):
            wrong = bytearray(ram);wrong[address]^=1
            with self.assertRaises(ValueError):independent(wrong,case)
