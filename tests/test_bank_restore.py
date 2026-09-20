import inspect
from pathlib import Path
import unittest
from tools.build_native import build
from tools.check_bank_restore import expected


class BankRestoreTests(unittest.TestCase):
    def test_default_off_and_scheduler_gate(self):
        self.assertIs(inspect.signature(build).parameters['experimental_bank_restore'].default,False)
        with self.assertRaisesRegex(ValueError,'NMI-only'):
            build(Path('missing'),[],Path('unused'),experimental_bank_restore=True,experimental_raster=True)

    def test_bank_mapping_does_not_depend_on_r7(self):
        for fc in range(256):
            for fd in (0,1,127,255):
                result=expected(fc,fd,0,0x75)
                self.assertEqual(result[4],0x81+((fc&15)>>1))
                self.assertEqual(result[7],0xc1+((fc&15)>>1))
                self.assertEqual(result[14],fd)
                self.assertEqual(result[1]&0xc3,0x43)

    def test_pending_edge_requires_both_owners_clear(self):
        for fc in range(256):
            self.assertEqual(expected(fc,255,7,0x30,True,True)[-1],int(fc&3==0))
