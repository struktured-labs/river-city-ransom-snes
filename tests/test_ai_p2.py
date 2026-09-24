import unittest

from tools.ai_p2_policy import (
    AI_TILES, DOWN, LEFT, RIGHT, UP, companion_caption, follow_p1_motion, lane_first,
    match_p1_horizontal, pick_ai_target, pick_p1_focus, shop_join_ready, should_flee,
    stuck_step,
)
from tools.build_ai_p2 import patch,HOOK,SLOT,SIZE
from tools.review_ai_p2 import evaluate


class AiP2Tests(unittest.TestCase):
    def parent(self):
        data=bytearray(b'\xff'*0x200000)
        for bank in range(1,9):data[bank*65536+HOOK:bank*65536+HOOK+3]=bytes.fromhex('4c8c34')
        return data

    def test_patches_only_verified_replicated_hooks_and_padding(self):
        data=self.parent();new=patch(data,bytes(SIZE),0x348c)
        for bank in range(1,9):
            self.assertEqual(new[bank*65536+HOOK:bank*65536+HOOK+3],bytes.fromhex('4c0069'))
            self.assertEqual(new[bank*65536+SLOT:bank*65536+SLOT+SIZE],bytes(SIZE))

    def test_rejects_occupied_code_and_changed_hook(self):
        for at in (8*65536+SLOT,6*65536+HOOK):
            data=self.parent();data[at]^=1
            with self.assertRaises(ValueError):patch(data,bytes(SIZE),0x348c)

    def test_default_off_audit_rejects_synthetic_p2_and_enabled_bit(self):
        ram=bytearray(2048);state=bytearray(16)
        row=dict(phase='menu',fault=None,input_requested=[],input_delivered=[],game_ram_hex=ram.hex())
        self.assertTrue(all(evaluate([row],[state.hex()],disabled=True).values()))
        ram[0xf1]=1;row['game_ram_hex']=ram.hex()
        self.assertFalse(evaluate([row],[state.hex()],disabled=True)['no_synthetic_p2'])
        state[0]=1
        self.assertFalse(evaluate([row],[state.hex()],disabled=True)['default_off'])

    def test_missing_management_and_equipment_evidence_does_not_pass(self):
        ram=bytes(2048);row=dict(frame=1,phase='irrelevant',fault=None,input_requested=[],input_delivered=[],game_ram_hex=ram.hex())
        result=evaluate([row],[bytes(16).hex()])
        self.assertFalse(result['exit_restores_p1_and_ai'])
        self.assertFalse(result['manage_belongings_exclusive_p2'])
        with self.assertRaises(ValueError):evaluate([row],[bytes(16).hex()],equipment=True)

    def test_equipment_gate_rejects_wrong_owner_inventory_and_stats(self):
        ram=bytearray(2048);ram[0x64d]=0x23;ram[0x655:0x657]=bytes([0x21,0xa2]);ram[0x59d]=1
        ram[0x4a3]=ram[0x4af]=15;ram[0x4a4]=25;ram[0x4b0]=45
        seed=dict(frame_before=1,p1_inventory=ram[0x64d:0x655].hex(),p1_stats=[15,15])
        def check(data):
            rows=[dict(frame=i+1,phase='p2_equipment_complete',fault=None,input_requested=[],
                       input_delivered=[],game_ram_hex=data.hex()) for i in range(5)]
            return evaluate(rows,[bytes(16).hex()]*5,equipment=True,seed=seed)
        expected=check(ram)
        for at,gate in [(0x64d,'p1_inventory_and_equipment_stats_untouched'),
                        (0x656,'p2_old_shoes_unequipped_new_shoes_equipped'),
                        (0x4b0,'p2_original_equipment_stats'),(0x59d,'original_item_owner_is_p2')]:
            self.assertTrue(expected[gate]);mutant=bytearray(ram);mutant[at]^=1
            self.assertFalse(check(mutant)[gate])

    def test_ai_skips_p1_focus_and_follows_when_that_is_the_only_goon(self):
        two = [(2, 10, 4, True), (3, 40, 8, True)]
        self.assertEqual(pick_p1_focus(two), 2)
        self.assertEqual(pick_ai_target(2, two), 3)
        only = [(2, 12, 3, True), (3, 20, 4, False)]
        self.assertEqual(pick_p1_focus(only), 2)
        self.assertEqual(pick_ai_target(2, only), 0)
        none = [(2, 90, 2, True), (3, 85, 5, True)]
        self.assertEqual(pick_p1_focus(none), 0xFF)
        from_p2 = [(2, 40, 5, True), (3, 25, 5, True)]
        self.assertEqual(pick_ai_target(0xFF, from_p2), 3)

    def test_lane_first_drops_x_when_depth_is_wrong(self):
        self.assertEqual(lane_first(40, 12, RIGHT | UP), UP)
        self.assertEqual(lane_first(10, 12, RIGHT | UP), RIGHT | UP)
        self.assertEqual(lane_first(40, 2, RIGHT), RIGHT)

    def test_stuck_detour_cycles_up_down_then_reverse(self):
        stuck, detour, out = 0, 0, RIGHT
        for _ in range(12):
            stuck, detour, out = stuck_step(stuck, detour, out, moved=False)
        self.assertEqual((detour, out & 0xF0), (1, UP))
        stuck, detour, out = 11, 1, RIGHT
        stuck, detour, out = stuck_step(stuck, detour, out, moved=False)
        self.assertEqual((detour, out & 0xF0), (2, DOWN))
        stuck, detour, out = 11, 2, RIGHT
        stuck, detour, out = stuck_step(stuck, detour, out, moved=False)
        self.assertEqual((detour, out & 0xF0), (3, LEFT))

    def test_shop_join_only_presses_up_when_on_p1(self):
        self.assertTrue(shop_join_ready(2, 3))
        self.assertFalse(shop_join_ready(20, 2))
        self.assertFalse(shop_join_ready(2, 20))
        self.assertFalse(shop_join_ready(0, 0, dxhi=1))

    def test_up_at_door_does_not_keep_forcing_horizontal(self):
        # P1 Up ($10): shop/door — do not apply walk-follow L/R
        self.assertEqual(match_p1_horizontal(0x10, 0), 0)
        self.assertEqual(follow_p1_motion(0, 0), 0)

    def test_ai_does_not_walk_against_p1_held_direction(self):
        self.assertEqual(match_p1_horizontal(RIGHT, LEFT | UP), RIGHT | UP)
        self.assertEqual(match_p1_horizontal(LEFT, RIGHT | DOWN), LEFT | DOWN)
        self.assertEqual(match_p1_horizontal(0, LEFT), LEFT)

    def test_ai_flees_when_p1_hits_ground_dying(self):
        self.assertFalse(should_flee(31, 0, 1))   # airborne stam 0: wait to land
        self.assertTrue(should_flee(0, 0, 1))     # landed, stam 0
        self.assertTrue(should_flee(0, 20, 6))    # grounded KO/getup flash
        self.assertFalse(should_flee(0, 40, 1))   # standing, has stam

    def test_ai_follows_p1_world_x_motion_not_combat(self):
        self.assertEqual(follow_p1_motion(3, LEFT | UP), RIGHT | UP)
        self.assertEqual(follow_p1_motion(-2, RIGHT | DOWN), LEFT | DOWN)
        self.assertEqual(follow_p1_motion(0, LEFT), LEFT)

    def test_companion_caption_is_p2_name_plus_ai(self):
        ryan=bytes([0xD1,0xD8,0xC0,0xCD])
        alex=bytes([0xC0,0xCB,0xC4,0xD7])
        self.assertEqual(companion_caption(ryan), ryan+bytes([0,0xC0,0xC8]))
        self.assertEqual(companion_caption(alex), alex+bytes([0,0xC0,0xC8]))
        self.assertNotEqual(companion_caption(ryan), AI_TILES)

    def test_follow_audit_keeps_companion_name(self):
        ram=bytearray(2048)
        ram[0x677:0x67b]=AI_TILES
        rows=[dict(frame=i+1,phase='ai_follow',fault=None,input_requested=[],
                   input_delivered=[],game_ram_hex=ram.hex()) for i in range(8)]
        states=[bytes(16).hex()]*8
        self.assertFalse(evaluate(rows,states).get('hud_companion_keeps_name'))
        ram[0x677:0x67b]=bytes([0xD1,0xD8,0xC0,0xCD])  # RYAN
        rows=[dict(frame=i+1,phase='ai_follow',fault=None,input_requested=[],
                   input_delivered=[],game_ram_hex=ram.hex()) for i in range(8)]
        self.assertTrue(evaluate(rows,states)['hud_companion_keeps_name'])
