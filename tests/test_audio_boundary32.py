"""Exercise the actual patched CPX/branch bytes, including the retained failure."""
import unittest
from tools.build_audio_boundary32 import patch


def admits(code, line):
    # The earlier ninth-bit test rejects lines256+, independently of CPX.
    if line >= 256:
        return False
    pc = 0
    carry = False
    for _ in range(4):
        op, operand = code[pc:pc+2]
        pc += 2
        if op == 0xe0:
            carry = line >= operand
        elif op in (0x90, 0xb0):
            if (op == 0x90 and not carry) or (op == 0xb0 and carry):
                pc += operand
                return pc != 11
        else:
            raise ValueError('Unexpected instruction')
    return pc == 8  # Fall through to existing JSR7885, not the restore path.


class Boundary32Tests(unittest.TestCase):
    def setUp(self):
        self.image = bytearray(b'\xff' * (9 * 65536))
        for bank in range(1, 9):
            at = bank * 65536 + 0x7bb4
            self.image[at:at+8] = bytes.fromhex('e0309007e0f0b003')

    def test_only_cutoffs_and_checksum_change(self):
        changed, sites = patch(self.image)
        differences = {i for i, (a, b) in enumerate(zip(self.image, changed)) if a != b}
        self.assertEqual(set(sites), {b*65536+0x7bb5 for b in range(1, 9)})
        self.assertTrue(differences <= set(sites) | set(range(0xffdc, 0xffe0)))
        self.assertTrue(set(sites) <= differences)
        self.assertEqual(sum(changed) & 65535, int.from_bytes(changed[0xffde:0xffe0], 'little'))

    def test_all_beam_positions_and_real_old_failure(self):
        changed, _ = patch(self.image)
        for bank in range(1, 9):
            at = bank * 65536 + 0x7bb4
            old, new = self.image[at:at+8], changed[at:at+8]
            for line in range(262):
                self.assertEqual(admits(old, line), 48 <= line < 240)
                self.assertEqual(admits(new, line), 32 <= line < 240)
            self.assertFalse(admits(old, 40))
            self.assertTrue(admits(new, 40))

    def test_changed_guard_or_branch_fails_closed(self):
        for offset in range(8):
            damaged = self.image.copy()
            damaged[8*65536+0x7bb4+offset] ^= 1
            with self.assertRaisesRegex(ValueError, 'eligibility'):
                patch(damaged)
