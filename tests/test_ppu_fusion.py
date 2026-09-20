import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.build_native import stub
from tools.build_ppu_fusion_trial import patch, targets, NAMES, HELPER, SIZE, PREFIX
from tools.check_ppu_fusion import independent, matrix
from tools.ppu_fusion_replay import guarded_variant


class PpuFusionTests(unittest.TestCase):
    def fixture(self):
        image = bytearray(b'\xff'*0x200000)
        rows, at = [], 0x6000
        for opcode, operand, resume in ((0x8d,0x2000,0xff7f), (0x8d,0x2003,None),
                (0x8e,0x2005,None), (0x8c,0x2006,None), (0x9d,0x2000,None),
                (0x8d,0x8000,None)):
            body = stub(opcode,operand,0x2301,resume=resume)
            rows.append(dict(stub=at,opcode=opcode,operand=operand))
            for bank in range(1,9):
                base = bank*65536
                image[base+0x2301:base+0x2301+len(PREFIX)] = PREFIX
                image[base+at:base+at+len(body)] = body
            at += len(body)
        entries = {name:HELPER+16*i for i,name in enumerate(NAMES.values())}
        return image, b'\xea'*SIZE, entries, dict(stub_bytes=at-0x6000,patches=rows)

    def test_exact_caller_scope_and_all_mirrors(self):
        image,helper,entries,meta = self.fixture()
        new,records,sites = patch(image,helper,entries,0x2301,meta)
        self.assertEqual(len(records),4)
        self.assertEqual(len(sites),32)
        self.assertEqual(records[0]['resume'],0xff7f)
        allowed = set(range(0xffdc,0xffe0))
        for bank in range(1,9):
            base = bank*65536
            allowed.update(range(base+HELPER,base+HELPER+SIZE))
            self.assertEqual(new[base+0x2301:base+0x2301+len(PREFIX)],PREFIX)
        for row in sites:
            allowed.update((row['site'],row['site']+1))
        self.assertTrue(all(i in allowed for i,(a,b) in enumerate(zip(image,new)) if a!=b))
        with self.assertRaises(ValueError):patch(new,helper,entries,0x2301,meta)

    def test_reject_modified_tail_save_restore_or_bank(self):
        image,helper,entries,meta = self.fixture()
        records = targets(image,meta,0x2301)
        for bank in range(1,9):
            for offset in (records[0]['start']+3, records[0]['end']-2, HELPER):
                bad = bytearray(image);bad[bank*65536+offset]^=1
                with self.assertRaises(ValueError):patch(bad,helper,entries,0x2301,meta)

    def test_matrix_covers_stubs_ownership_ports_and_beam(self):
        image,_,_,meta = self.fixture()
        cases = matrix(targets(image,meta,0x2301))
        self.assertEqual(len(cases),96)
        self.assertEqual({c['BANK'] for c in cases},set(range(0xc1,0xc9)))
        self.assertEqual({c['WAITLINE'] for c in cases},{40,241})
        self.assertEqual({c['STACK'] for c in cases},{0x20,0x80,0xff})
        self.assertEqual({(c['DEPTH'],c['PAIR'],c['TASK']) for c in cases},
                         {(0,0,0xc0),(1,0,0xc0),(0,1,0xc0),(1,1,0)})

    def test_independent_oracle_rejects_nmi_abi_and_dirty_mutations(self):
        c = dict(INPUT_A=0x18,INPUT_X=0xa6,INPUT_Y=0x59,OLD_CTRL=0x18,
            LATCH=0,DEPTH=1,PAIR=0,FLAGS=0x35,STACK=255,OPCODE=0x8d,
            ADDRESS=0x2000,RESUME=0,TASK=0xc0,WAITLINE=40)
        ram = bytearray(131072)
        ram[0x1b00:0x1e00] = b'\x5a'*0x300
        for address,value in ((0x1b20,0),(0x1b21,0x20),(0x1b22,0x18),
            (0x1c20,0x18),(0x1c25,0),(0x1c27,0x20),(0x1c26,0x1f),
            (0x1c18,0),(0x1c06,0),(0x1c60,1),(0x1c61,0),(0x1c0a,1),
            (0x1c83,0),(0x1c6a,0)):
            ram[address] = value
        ram[0x6000:0x6009] = bytes.fromhex('181b35a659341283ff')
        self.assertEqual(independent(ram,c),dict(enabled=False,pending_delivered=False,return_in_vblank=False))
        for address in (0x1cbb,0x1b22,0x1c6a,0x6001,0x6002,0x6005,0x600a,0x600b):
            bad = bytearray(ram);bad[address]^=1
            with self.assertRaises(ValueError):independent(bad,c)

    def test_replay_rejects_inflight_stub_and_private_helper(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ('native_boot.lbl','native_runtime.lbl'):
                (root/name).write_text('al 002301 .dispatch_write\nal 0028A4 .mark_ppu_dirty\n')
            for pc in (0xc16000,0xc168ef,0xc17000,0xc170ff,0xc12301):
                with self.assertRaisesRegex(ValueError,'Checkpoint inside changed path'):
                    guarded_variant(root,root,'fusion',pc)


if __name__ == '__main__':
    unittest.main()
