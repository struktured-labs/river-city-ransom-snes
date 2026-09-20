import unittest

from tools.audit_route_store_latency import segments


class RouteStoreLatencyTests(unittest.TestCase):
    def fixture(self):
        rows=[];rendered={}
        for room in range(4):
            ram=bytearray(2048);ram[0x42]=room;ram[0x100]=192;ram[0x692]=4
            for _ in range(8):
                frame=len(rows)+1
                rows.append(dict(frame=frame,game_ram_hex=ram.hex(),
                    native=dict(ppu_mask=8,transition_state=0)))
                rendered[frame]=[frame%512]
        return rows,rendered

    def test_four_rooms_and_room_boundaries_retained(self):
        phases,excluded=segments(*self.fixture())
        self.assertEqual(set(phases),{f'room{r}.segment00' for r in range(4)})
        self.assertEqual([p['frames'] for p in phases.values()],[7]*4)
        self.assertEqual([e['frame'] for e in excluded],[1,9,17,25])

    def test_missing_or_split_actual_render_fails(self):
        for cameras in (None,[],[2,3]):
            rows,rendered=self.fixture()
            if cameras is None:del rendered[2]
            else:rendered[2]=cameras
            with self.assertRaisesRegex(ValueError,'Missing/split'):segments(rows,rendered)

    def test_invalid_rendered_camera_fails(self):
        rows,rendered=self.fixture();rendered[2]=[512]
        with self.assertRaisesRegex(ValueError,'Invalid camera'):segments(rows,rendered)

    def test_missing_room_is_not_a_full_route_pass(self):
        rows,rendered=self.fixture()
        with self.assertRaisesRegex(ValueError,'Missing room'):segments(rows[:24],rendered)

    def test_missing_timeline_frame_is_not_bridged(self):
        rows,rendered=self.fixture();del rows[3]
        with self.assertRaisesRegex(ValueError,'Nonconsecutive'):segments(rows,rendered)

    def test_disabled_transition_and_pause_split_segments(self):
        for kind in ('disabled','transition','pause'):
            rows,rendered=self.fixture()
            if kind=='disabled':rows[3]['native']['ppu_mask']=0
            elif kind=='transition':rows[3]['native']['transition_state']=1
            else:
                ram=bytearray.fromhex(rows[3]['game_ram_hex']);ram[0x107]=128
                rows[3]['game_ram_hex']=ram.hex()
            phases,excluded=segments(rows,rendered)
            self.assertEqual([r['frame'] for r in phases['room0.segment00']['series']],[2,3])
            self.assertEqual([r['frame'] for r in phases['room0.segment01']['series']],[6,7,8])
            self.assertTrue({4,5}.issubset({r['frame'] for r in excluded}))

    def test_single_frame_segment_retained_as_exclusion(self):
        rows,rendered=self.fixture();rows[2]['native']['ppu_mask']=0
        phases,excluded=segments(rows,rendered)
        self.assertIn(dict(frame=2,reason='Single-frame stable segment'),excluded)
        self.assertEqual(phases['room0.segment00']['series'][0]['frame'],5)

    def test_original_nes_uses_actual_ppu_mask(self):
        rows,rendered=self.fixture()
        for row in rows:
            del row['native'];row['nes_ppu']=dict(mask=8)
        rows[3]['nes_ppu']['mask']=0
        phases,excluded=segments(rows,rendered,'nes')
        self.assertEqual([r['frame'] for r in phases['room0.segment01']['series']],[6,7,8])
        self.assertTrue({4,5}.issubset({r['frame'] for r in excluded}))

    def test_unknown_system_rejected(self):
        with self.assertRaisesRegex(ValueError,'Unsupported system'):
            segments(*self.fixture(),system='other')
