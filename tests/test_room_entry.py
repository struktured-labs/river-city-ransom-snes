import unittest
from tools.audit_room_entry import entries, load_anchors, visibility_latencies, no_later
from tools.build_native import build
from pathlib import Path


def sample(room,mask,task=192):
    raw=bytearray(2048);raw[0x42]=room;raw[0x100]=task
    return dict(game_ram_hex=raw.hex(),nes_ppu=dict(mask=mask))


class RoomEntryTests(unittest.TestCase):
    def test_load_anchors_include_work_before_enable(self):
        rows=[sample(0,24),sample(0,0),sample(1,0),sample(1,0),sample(1,24)]
        for i,row in enumerate(rows):row['frame']=i+100
        anchors=load_anchors(rows,4)
        self.assertEqual(anchors,dict(room_change_frame=102,rendering_off_frame=101,enable_frame=104))
        self.assertEqual(visibility_latencies(anchors,7),dict(first_visible_frame=111,
            room_change_to_visible=9,rendering_off_to_visible=10))

    def test_pre_enable_delay_cannot_manufacture_speed_pass(self):
        nes=visibility_latencies(dict(enable_frame=120,room_change_frame=100,rendering_off_frame=100),7)
        snes=visibility_latencies(dict(enable_frame=140,room_change_frame=100,rendering_off_frame=100),1)
        self.assertFalse(no_later(nes,snes,'room_change_to_visible'))
        self.assertFalse(no_later(nes,snes,'rendering_off_to_visible'))

    def test_missing_visibility_is_failure(self):
        anchors=dict(enable_frame=120,room_change_frame=100,rendering_off_frame=100)
        self.assertFalse(no_later(visibility_latencies(anchors,7),visibility_latencies(anchors,None),'room_change_to_visible'))

    def test_missing_or_discontinuous_load_edges_rejected(self):
        for rows in ([sample(1,0),sample(1,24)],
                     [sample(0,24),sample(1,24)]):
            for i,row in enumerate(rows):row['frame']=i
            with self.assertRaises(ValueError):load_anchors(rows,len(rows)-1)
        rows=[sample(0,24),sample(1,0),sample(1,24)]
        for i,row in enumerate(rows):row['frame']=i*2
        with self.assertRaisesRegex(ValueError,'consecutive'):load_anchors(rows,2)

    def test_first_enable_edge_not_later_favorable_entry(self):
        rows=[sample(0,24)]
        for room in (1,2,3,2):rows += [sample(room,0),sample(room,24),sample(room,24)]
        self.assertEqual(entries(rows),{1:2,2:5,3:8})

    def test_shop_or_missing_edge_cannot_certify_room_entry(self):
        for rows in ([sample(r,24) for r in (1,2,3)],
                     [sample(r,m,0) for r in (1,2,3) for m in (0,24)]):
            with self.assertRaises(ValueError):entries(rows)

    def test_hidden_budget_bounds_precede_any_rom_access(self):
        for value in (0,17,-1):
            with self.assertRaisesRegex(ValueError,'Hidden row budget'):
                build(Path('nonexistent'),[],Path('unused'),experimental_hidden_rows=value)
        with self.assertRaisesRegex(ValueError,'Hidden row budget'):
            build(Path('nonexistent'),[],Path('unused'),experimental_hidden_rows=8,experimental_transition_wait_prepare=True)
