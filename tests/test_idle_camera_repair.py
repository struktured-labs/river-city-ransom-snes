import unittest

from tools.repair_idle_camera_log import repair


class IdleCameraRepairTests(unittest.TestCase):
    def fixture(self):
        image = bytearray(b'\xff'*0x200000)
        image[0xE000:0xE016] = bytes.fromhex('eaeaea08c22048da5ae2208b9080a9018002a90048ad')
        return image

    def test_opcode_operand_and_target(self):
        before = self.fixture()
        after = repair(before)
        self.assertEqual(after[0xE00C], 0x80)
        target = 0xE00E+int.from_bytes(after[0xE00D:0xE00E], 'little', signed=True)
        self.assertEqual(target, 0xE012)
        self.assertEqual(after[target:target+2], bytes.fromhex('a900'))
        self.assertEqual(before[0xE00C:0xE00E], bytes.fromhex('9080'))
        changed = {i for i, (a, b) in enumerate(zip(before, after)) if a != b}
        self.assertLessEqual(changed, {0xE00C, 0xE00D, *range(0xFFDC, 0xFFE0)})

    def test_changed_or_already_repaired_entry_rejected(self):
        for index in (0xE00C, 0xE00D, 0xE012):
            image = self.fixture()
            image[index] ^= 1
            with self.assertRaises(ValueError):
                repair(image)
        with self.assertRaises(ValueError):
            repair(repair(self.fixture()))
