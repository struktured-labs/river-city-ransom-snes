import unittest
from pathlib import Path
from tools.build_final_vblank_window import HELPER,patch


def execute(code,line):
    pc=0;a=0;carry=False
    for _ in range(12):
        op=code[pc];pc+=1
        if op==0xa5:
            if code[pc]!=0x1c:raise ValueError('Wrong latched beam')
            pc+=1;a=line
        elif op==0xc9:carry=a>=code[pc];pc+=1
        elif op in (0x90,0xb0):
            delta=code[pc];pc+=1
            if carry==(op==0xb0):pc+=delta if delta<128 else delta-256
        elif op==0x38:carry=True
        elif op==0x18:carry=False
        elif op==0x60:return carry
        else:raise ValueError('Unexpected opcode')
    raise ValueError('No return')


class FinalWindowTests(unittest.TestCase):
    def test_all_low_beam_values(self):
        for line in range(256):
            self.assertEqual(execute(HELPER,line),240<=line<254)

    def test_actual_old_gate_accepts_wrapped_zero(self):
        old=bytes.fromhex('a51cc9feb00238601860')
        self.assertTrue(execute(old,0))
        self.assertFalse(execute(HELPER,0))
        for line in range(240,256):self.assertEqual(execute(old,line),execute(HELPER,line))

    def test_guarded_patch_preserves_hardware_checks_and_rejection_target(self):
        original=Path('build/overflow-3526/postrow-stop-game-3764/native-cpu.sfc').read_bytes()
        result,_=patch(original)
        self.assertEqual(result[0x86c8:0x86dc],original[0x86c8:0x86dc])
        self.assertEqual(result[0x86e4:0x86e6],bytes.fromhex('1860'))
        self.assertEqual(result[0x77d0:0x77d0+len(HELPER)],HELPER)
        bad=bytearray(original);bad[0x86c8]=0xea
        with self.assertRaises(ValueError):patch(bad)
