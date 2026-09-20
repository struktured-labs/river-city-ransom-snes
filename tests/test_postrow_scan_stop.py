"""Execute the emitted post-row gate's two paths; real trace tests cover MMIO."""
import hashlib
from pathlib import Path
import unittest


def execute(code, admitted):
    pc=0; wide=True; checked=False
    for _ in range(8):
        op=code[pc];pc+=1
        if op in (0xe2,0xc2):
            if code[pc]!=0x20:raise ValueError('Wrong width control')
            pc+=1;wide=op==0xc2
        elif op==0x20:
            target=int.from_bytes(code[pc:pc+2],'little');pc+=2
            if target!=0x87e4 or wide:raise ValueError('Wrong row-room call')
            checked=True
        elif op==0x90:
            delta=code[pc];pc+=1
            if not checked:raise ValueError('Uninitialized carry')
            if not admitted:pc+=delta if delta<128 else delta-256
        elif op==0x4c:
            return int.from_bytes(code[pc:pc+2],'little'),wide
        else:raise ValueError('Unexpected instruction')
    raise ValueError('No bounded exit')


class PostrowStopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.image=Path('build/overflow-3526/postrow-stop-game-3764/native-cpu.sfc').read_bytes()
        if hashlib.sha256(cls.image).hexdigest()!='8ed9aafe6af975023bfd7fd24a9ca0419a6b82db7916099dc6ef2c31f902cc29':
            raise ValueError('Changed cartridge')
        cls.code=cls.image[0x77c0:0x77cf]

    def test_both_continuations(self):
        self.assertEqual(execute(self.code,True),(0x7380,True))
        self.assertEqual(execute(self.code,False),(0x844f,False))
        self.assertEqual(self.image[0x844c:0x844f],bytes.fromhex('4cc077'))
        self.assertEqual(self.image[0x844f:0x8451],bytes.fromhex('e220'))
        self.assertEqual(self.image[0x86dc:0x86e6],bytes.fromhex('a51cc9feb00238601860'))

    def test_wrong_branch_rejected(self):
        bad=bytearray(self.code);bad[6]=4
        with self.assertRaises(ValueError):execute(bad,False)

    def test_wrong_gate_rejected(self):
        bad=bytearray(self.code);bad[3]=0xe5
        with self.assertRaises(ValueError):execute(bad,True)
