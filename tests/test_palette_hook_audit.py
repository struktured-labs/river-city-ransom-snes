import unittest
from tools.audit_palette_hook import copied_pairs


class PaletteHookAuditTests(unittest.TestCase):
    def fixture(self):
        rom=bytearray(512);rows=[]
        for i in range(32):
            pc=i*7;target=0x7f3f00+(i-16 if i in (16,20,24,28) else i)
            rom[pc:pc+7]=b'\xad'+(0x110+i).to_bytes(2,'little')+b'\x8f'+target.to_bytes(3,'little')
            rows.extend((dict(pc=0xc00000+pc,opcode=0xad),dict(pc=0xc00000+pc+3,opcode=0x8f)))
        return rows,rom

    def test_all_original_source_alias_pairs(self):
        self.assertEqual(len(copied_pairs(*self.fixture())),32)

    def test_missing_pair(self):
        rows,rom=self.fixture()
        with self.assertRaisesRegex(ValueError,'order'):
            copied_pairs(rows[:-2],rom)

    def test_wrong_alias(self):
        rows,rom=self.fixture();rom[16*7+4]=16
        with self.assertRaisesRegex(ValueError,'aliases'):
            copied_pairs(rows,rom)

    def test_wrong_source(self):
        rows,rom=self.fixture();rom[1]=17
        with self.assertRaisesRegex(ValueError,'order'):
            copied_pairs(rows,rom)
