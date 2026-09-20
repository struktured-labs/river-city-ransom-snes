import struct
import unittest

from tools.check_final_batch_margin import verify


class FinalBatchMarginTests(unittest.TestCase):
    def fixture(self):
        ram=bytearray(131072);ram[0x1e1c]=250;ram[0x1c7e]=5;ram[0x1c7f]=1
        ram[0x1d00]=ram[0x1d7f]=3;ram[0x1e80]=1
        original=bytes(i^0x17 for i in range(32));shadow=bytes(v^0x55 for v in original)
        ram[0x110:0x130]=original;ram[0x13f00:0x13f20]=shadow;ram[0x5580:0x55a0]=shadow
        colors=[i*509 for i in range(64)];image=struct.pack('<64H',*colors)
        bg=[0x1234]*64;obj=[0x1234]*64
        bg[:16]=[colors[original[16 if i%4==0 else i]&63] for i in range(16)]
        for i in range(16):obj[(i//4)*16+i%4]=colors[(shadow[16+i] if i%4==0 else original[16+i])&63]
        ram[0x5400:0x5480]=struct.pack('<64H',*bg);ram[0x5500:0x5580]=struct.pack('<64H',*obj)
        cgram=[0]*256;cgram[:16]=bg[:16]
        for i in range(16):cgram[128+(i//4)*16+i%4]=obj[(i//4)*16+i%4]
        ram[0x6500:0x6700]=struct.pack('<256H',*cgram)
        return ram,image,dict(depth=1)

    def test_latest_legal_conversion_preserves_real_palette_and_oam(self):
        ram,image,c=self.fixture();r=verify(ram,image,0,c)
        self.assertTrue(r['palette_converted']);self.assertEqual(r['finish_line'],261)

    def test_overrun_stale_cgram_and_lost_ownership_rejected(self):
        ram,image,c=self.fixture()
        for at in (0x1c7b,0x1d00,0x1e80,0x110,0x13f00,0x5580,0x6500,0x6602,0x6200):
            bad=bytearray(ram);bad[at]^=1
            with self.assertRaises(ValueError):verify(bad,image,0,c)
        ram[0x1c7e]=6
        with self.assertRaises(ValueError):verify(ram,image,0,c)


if __name__=='__main__':unittest.main()
