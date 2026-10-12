from pathlib import Path
import unittest
from tools.build_autojoy_coroutine_fix import patch,TAIL,SITE

class CoroutineTail(unittest.TestCase):
    def test_no_stack_operations_in_enable_tail(self):
        # Exact ORA #1 / STA $4200 / JMP $FC73; no JSR/PHP/PHA window.
        self.assertEqual(TAIL,bytes.fromhex('09018d00424c73fc'))
        for a in range(0x80,0x100):
            self.assertTrue(a|1)  # FC60's BNE remains taken until NMI consumes it
            self.assertEqual((a|1)&0x80,a&0x80)

    def test_old_stackful_tail_is_replaced_in_all_banks(self):
        rom=bytearray(b'\xff'*0x200000)
        for bank in range(1,9):rom[(bank<<16)+0x640e:(bank<<16)+0x6416]=SITE
        b,changes=patch(rom)
        self.assertEqual(len(changes),8)
        for c in changes:
            self.assertEqual(b[c['hook']:c['hook']+3],bytes.fromhex('4c006f'))
            self.assertEqual(b[c['trampoline']:c['trampoline']+8],TAIL)
        with self.assertRaises(ValueError):patch(b)

    def test_occupied_slot_rejected(self):
        rom=bytearray(b'\xff'*0x200000)
        for bank in range(1,9):rom[(bank<<16)+0x640e:(bank<<16)+0x6416]=SITE
        rom[0x16f00]=0
        with self.assertRaises(ValueError):patch(rom)
