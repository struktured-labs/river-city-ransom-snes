"""Execute emitted producer helper, independently checking bounds and staging flags."""
import unittest
from tools.producer_group_scan import assemble, patch


def execute(code, x, budget, flags):
    pc = 0; a = 0; carry = False; zero = False; wide = False; reads = []
    def byte():
        nonlocal pc
        value = code[pc]; pc += 1; return value
    def word(): return byte() | byte() << 8
    def immediate(): return word() if wide else byte()
    for _ in range(80):
        op = byte(); mask = 65535 if wide else 255
        if op == 0xe0:
            n = word(); carry = x >= n; zero = x == n
        elif op == 0xc9:
            n = immediate(); carry = (a & mask) >= n; zero = (a & mask) == n
        elif op in (0xb0,0x90,0xd0,0xf0):
            delta = byte()
            if {0xb0:carry,0x90:not carry,0xd0:not zero,0xf0:zero}[op]:
                pc += delta if delta < 128 else delta-256
        elif op in (0xc2,0xe2):
            if byte() != 0x20: raise AssertionError('Unexpected width change')
            wide = op == 0xc2
        elif op in (0xbd,0x1d):
            at = word()-0x1d00+x
            positions = range(at, at+(2 if wide else 1))
            if any(not 0 <= i < 128 for i in positions): raise AssertionError('Read past flags')
            reads.extend(positions)
            v = flags[at] | (flags[at+1] << 8 if wide else 0)
            a = (a & ~mask) | (v if op == 0xbd else (a & mask) | v)
            zero = (a & mask) == 0
        elif op == 0x29:
            a = (a & ~mask) | ((a & mask) & immediate()); zero = (a & mask) == 0
        elif op == 0x8a:
            a = (a & ~mask) | (x & mask); zero = (a & mask) == 0
        elif op == 0x18: carry = False
        elif op == 0x38: carry = True
        elif op in (0x69,0xe9):
            n = immediate(); total = (a & mask)+n+int(carry) if op == 0x69 else (a & mask)-n-int(not carry)
            carry = total > mask if op == 0x69 else total >= 0
            a = (a & ~mask) | (total & mask); zero = (a & mask) == 0
        elif op == 0xaa: x = a; zero = x == 0
        elif op == 0xa2: x = word(); zero = x == 0
        elif op == 0xad:
            if word() != 0x1c6c: raise AssertionError('Unexpected RAM read')
            a = (a & ~255) | budget; zero = budget == 0
        elif op == 0x8d:
            if word() != 0x1c6c or wide: raise AssertionError('Unexpected RAM write')
            budget = a & 255
        elif op == 0x4c: return x, budget, word(), wide, zero, reads
        else: raise AssertionError(hex(op))
    raise AssertionError('No exit')


class ProducerGroupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.code = assemble()

    def test_exhaustive_empty_and_ready_only_ring_budget_bounds(self):
        for flag in (0,2):
            for x in range(128):
                for budget in range(1,129):
                    result = execute(self.code,x,budget,bytes([flag]*128))
                    if x <= 120 and budget >= 8:
                        expected = ((x+8)%128,budget-8,0x888e if budget == 8 else 0x8872)
                    else: expected = (x,budget,0x8879)
                    self.assertEqual(result[:3],expected)
                    self.assertFalse(result[3])

    def test_every_dirty_or_dirty_ready_row_prevents_group_skip(self):
        for x in range(121):
            for at in range(x,x+8):
                for flag in (1,3):
                    flags = bytearray(128); flags[at] = flag
                    result = execute(self.code,x,128,flags)
                    self.assertEqual(result[:4],(x,128,0x8879,False))
                    self.assertEqual(result[4],flags[x] == 1)

    def test_wrong_dirty_mask_is_detected(self):
        bad = self.code.replace(bytes.fromhex('290101'),bytes.fromhex('290202'))
        self.assertNotEqual(bad,self.code)
        flags = bytearray(128); flags[3] = 1
        self.assertNotEqual(execute(bad,0,128,flags)[:3],execute(self.code,0,128,flags)[:3])

    def test_wrong_parent_rejected(self):
        with self.assertRaises(ValueError): patch(b'\xff'*0x10000,self.code)


if __name__ == '__main__': unittest.main()
