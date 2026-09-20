import unittest
from tools.check_movement import compare_positions,head_x


class MovementTests(unittest.TestCase):
    def test_relocated_unique_head_and_ambiguous_duplicate(self):
        ram=bytearray(2048)
        head=bytes((116,1,64,40,116,0,64,48))
        for slot in (0x200,0x2CC,0x2F8):
            ram=bytearray(2048)
            ram[slot:slot+8]=head
            self.assertEqual(head_x({'game_ram_hex':ram.hex()}),40)
        ram[0x200:0x208]=head
        with self.assertRaises(ValueError):head_x({'game_ram_hex':ram.hex()})

    def test_head_signature_accepts_one_pixel_walk_bob(self):
        for y in (115,116):
            ram=bytearray(2048)
            ram[0x2F8:0x300]=bytes((y,1,64,40,y,0,64,48))
            self.assertEqual(head_x({'game_ram_hex':ram.hex()}),40)
    def test_equal_speed_passes_and_delayed_motion_fails(self):
        positions=[40+i//2 for i in range(32)]
        self.assertTrue(compare_positions(positions,positions)['passed'])
        slower=[40]+positions[:-1]
        self.assertFalse(compare_positions(positions,slower)['passed'])
        self.assertFalse(compare_positions(positions,[40]*32)['passed'])

    def test_wrong_actor_signature_rejected(self):
        with self.assertRaises(ValueError):head_x({'game_ram_hex':bytes(2048).hex()})

    def test_backward_motion_rejected(self):
        with self.assertRaises(ValueError):compare_positions([40]*32,[40,39]+[40]*30)
