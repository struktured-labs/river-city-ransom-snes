import unittest

from tools.audit_load_off_cost import original_wait_cost


class OriginalWaitCostTests(unittest.TestCase):
    def fixture(self):
        image = bytearray(0x400000)
        image[0x2fc73:0x2fc75] = b'\xd0\xfe'
        rows = [dict(frame=10, pc=0xc2fc73, opcode=0xd0, clock=100),
                dict(frame=10, pc=0xc2fc73, opcode=0xd0, clock=118),
                dict(frame=10, pc=0x008000, opcode=0x08, clock=160),
                dict(frame=11, pc=0xc2fc73, opcode=0xd0, clock=300),
                dict(frame=11, pc=0xc2fc75, opcode=0xa5, clock=318)]
        return rows, image

    def test_bound_window_keeps_boundary_event_elapsed(self):
        rows, image = self.fixture()
        result = original_wait_cost(rows, image, 10, 11)
        self.assertEqual(result['executions'], 2)
        self.assertEqual(result['elapsed_clocks'], 60)

    def test_rom_operand_and_trace_opcode_are_verified(self):
        rows, image = self.fixture()
        image[0x2fc74] = 0
        with self.assertRaisesRegex(ValueError, 'branch changed'):
            original_wait_cost(rows, image, 10, 11)
        image[0x2fc74] = 0xfe
        rows[0]['opcode'] = 0x80
        with self.assertRaisesRegex(ValueError, 'branch changed'):
            original_wait_cost(rows, image, 10, 11)

    def test_non_game_bank_is_not_merged(self):
        rows, image = self.fixture()
        rows[0]['pc'] = rows[1]['pc'] = 0xc0fc73
        with self.assertRaisesRegex(ValueError, 'not observed'):
            original_wait_cost(rows, image, 10, 11)

    def test_bad_clocks_fail_closed(self):
        rows, image = self.fixture()
        rows[1]['clock'] = rows[0]['clock']
        with self.assertRaisesRegex(ValueError, 'Non-increasing'):
            original_wait_cost(rows, image, 10, 11)
