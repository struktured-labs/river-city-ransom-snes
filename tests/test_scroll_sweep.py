import unittest
from tools.audit_scroll_sweep import observations


def row(frame,camera=0,mask=0x1e,native=False,published=None):
    raw=bytearray(2048)
    raw[0x100]=0xc0
    raw[0xdc:0xde]=camera.to_bytes(2,'little')
    raw[0xf6]=camera&255
    raw[0x3d]=(camera>>8)&1
    result=dict(frame=frame,game_ram_hex=raw.hex(),phase='settle_street')
    if native:
        result['native']=dict(ppu_mask=mask,transition_state=0,hdma_street_scroll_x=camera&511 if published is None else published)
    else:result['nes_ppu']=dict(mask=mask)
    return result


class SweepTests(unittest.TestCase):
    def test_render_disabled_is_not_a_visible_camera_sample(self):
        first,stable,_=observations([row(1,mask=0),row(2,mask=0),row(3),row(4)])
        self.assertEqual(first[0,0]['frame'],3)
        self.assertEqual(stable[0,0]['frame'],4)

    def test_first_second_consecutive_sample_not_later_prettier_one(self):
        first,stable,_=observations([row(1,4),row(2,5),row(3,4),row(4,4),row(5,4)])
        self.assertEqual(first[0,4]['frame'],1)
        self.assertEqual(stable[0,4]['frame'],4)

    def test_ninth_scroll_bit_and_old_publication_caught(self):
        _,_,late=observations([row(1,256,native=True,published=0),row(2,512,native=True,published=0)])
        self.assertEqual(len(late),1)
        self.assertEqual(late[0]['expected'],256)

    def test_missing_visibility_fails_closed(self):
        broken=row(1)
        del broken['nes_ppu']
        with self.assertRaises(KeyError):observations([broken])

    def test_post_fade_uses_game_state_not_a_pretty_frame(self):
        rows=[row(i) for i in range(1,7)]
        for i,r in enumerate(rows):
            raw=bytearray.fromhex(r['game_ram_hex'])
            raw[0x692]=4 if i!=1 else 3
            raw[0x3e]=2 if i<3 else 4
            r['game_ram_hex']=raw.hex()
        first,stable,_=observations(rows,post_fade=True)
        self.assertEqual(first[0,0]['frame'],4)
        self.assertEqual(stable[0,0]['frame'],5)

    def test_post_fade_keeps_fading_scroll_publication_failures(self):
        first,stable,late=observations([row(1,256,native=True,published=0)],post_fade=True)
        self.assertFalse(first)
        self.assertFalse(stable)
        self.assertEqual(len(late),1)

    def test_post_fade_excludes_transient_boot_game_state(self):
        rows=[row(i) for i in range(1,5)]
        for i,r in enumerate(rows):
            raw=bytearray.fromhex(r['game_ram_hex']);raw[0x692]=4
            r['game_ram_hex']=raw.hex()
            if i<2:r['phase']='boot_to_menu'
        first,stable,_=observations(rows,post_fade=True)
        self.assertEqual(first[0,0]['frame'],3)
        self.assertEqual(stable[0,0]['frame'],4)
