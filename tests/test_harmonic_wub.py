import unittest

from tools.build_harmonic_wub_trial import helper, payload, patch, HELPER, CALLSITE
from tools.build_ident_spc import build as original
from tools.audit_harmonic_wub import comparison_gates


def execute_helper(volume, note):
    """Bounded instruction-level check, independent expected envelope below.

    Not an SPC timing/DSP model: the actual ROM is separately captured in Snes9x.
    """
    code = helper()
    a, y, carry, pc, stack, writes = volume, 73, False, 0, [], []
    for _ in range(32):
        op = code[pc]; pc += 1
        if op == 0x2d: stack.append(a)
        elif op == 0xae: a = stack.pop()
        elif op == 0x6d: stack.append(y)
        elif op == 0xee: y = stack.pop()
        elif op == 0xe4:
            assert code[pc] == 9
            pc += 1; a = note
        elif op == 0x68:
            carry = a >= code[pc]; pc += 1
        elif op == 0x90:
            offset = code[pc]; pc += 1
            if not carry: pc += offset if offset < 128 else offset-256
        elif op == 0xfd: y = a
        elif op == 0xcf:
            product = y*a; y, a = product >> 8, product & 255
        elif op == 0xdd: a = y
        elif op == 0x1c: a = (a*2) & 255
        elif op == 0x5c: a >>= 1
        elif op == 0xc4:
            assert code[pc] == 0xf3
            pc += 1; writes.append(a)
        elif op == 0x6f:
            assert not stack and y == 73
            return a, writes
        else: raise AssertionError(f'Unexpected opcode {op:02x}')
    raise AssertionError('Helper did not return')


class HarmonicWubTests(unittest.TestCase):
    def test_harmonic_gate_rejects_old_sound_and_louder_only(self):
        old = [dict(note=n,open_harmonic_to_bass=.04,contrast=2) for n in (144,174,204)]
        self.assertFalse(any(comparison_gates(old,old).values()))
        # A broadband loudness change does not change a band-power ratio.
        brighter_only = [dict(r,open_harmonic_to_bass=.08) for r in old]
        self.assertFalse(comparison_gates(brighter_only,old)['deeper_harmonic_motion'])
        good = [dict(r,open_harmonic_to_bass=.08,contrast=4) for r in old]
        self.assertTrue(all(comparison_gates(good,old).values()))

    def test_every_note_and_safe_volume_executes_preserving_y_stack(self):
        for note in range(240):
            for volume in range(117):
                expected = volume//2 if note < 144 else 2*(volume*volume//256)
                result, writes = execute_helper(volume, note)
                self.assertEqual((result, writes), (expected, [expected]))
                self.assertLess(result, 128)  # DSP signed-volume polarity

    def test_only_helper_call_and_padding_change_payload(self):
        old, new = original(), payload()
        self.assertEqual(len(old), len(new))
        call = old.index(CALLSITE)
        allowed = set(range(call,call+3)) | set(range(HELPER,HELPER+len(helper())))
        self.assertTrue(all(i in allowed for i,(a,b) in enumerate(zip(old,new)) if a != b))
        self.assertEqual(old[512:],new[512:])  # samples and directory untouched

    def test_cartridge_scope_and_repeated_patch_rejection(self):
        image = bytearray(b'\xff'*0x200000)
        old = original(); image[0x110800:0x110800+len(old)] = old
        new, offset = patch(image)
        allowed = set(range(offset,offset+len(old))) | set(range(0xffdc,0xffe0))
        self.assertTrue(all(i in allowed for i,(a,b) in enumerate(zip(image,new)) if a != b))
        with self.assertRaises(ValueError): patch(new)
        with self.assertRaises(ValueError): patch(image[:-1])
