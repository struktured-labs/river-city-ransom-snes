import struct
import unittest

from tools.audit_palette_pipeline import canonical_palette, bg_words, generations, delivery_offsets


def frame(level,dirty=True,source=None):
    raw=bytearray(2048);raw[0x692]=level;raw[0x3e]=8 if dirty else 0
    raw[0x110:0x130]=bytes(range(32)) if source is None else source
    return dict(frame=100+level,game_ram_hex=raw.hex())


class PalettePipelineTests(unittest.TestCase):
    def test_sequential_universal_alias_writes_replace_earlier_values(self):
        got=canonical_palette(bytes(range(32)))
        for index in range(32):
            expected=index+16 if index in (0,4,8,12) else 0 if index in (16,20,24,28) else index
            self.assertEqual(got[index],expected)
        with self.assertRaises(ValueError):canonical_palette(bytes(16))

    def test_background_transparency_and_six_bit_color_indices(self):
        colors=tuple(range(64));shadow=bytes(range(192,224))
        self.assertEqual(bg_words(shadow,colors),tuple(0 if i%4==0 else i for i in range(16)))

    def test_incomplete_palette_does_not_count_as_generation(self):
        rows=[frame(0,False)]+[frame(i) for i in range(4)]
        result=generations(rows,tuple(range(64)))
        self.assertEqual([result[i]['offset'] for i in range(4)],[1,2,3,4])

    def test_missing_and_out_of_order_generations_rejected(self):
        for levels in ((0,1,2),(1,0,2,3)):
            with self.assertRaises(ValueError):generations([frame(i) for i in levels],tuple(range(64)))

    def test_distinct_indices_can_legitimately_have_identical_rgb(self):
        colors=[0]*64;colors[0x20]=colors[0x30]=32767
        rows=[frame(i,source=bytes([0x20 if i<3 else 0x30])*32) for i in range(4)]
        result=generations(rows,colors)
        self.assertNotEqual(result[2]['source_indices'],result[3]['source_indices'])
        self.assertEqual(result[2]['words'],result[3]['words'])

    def fixture(self):
        generation=dict(offset=1,words=tuple(range(1,17)),source_indices='01'*16)
        empty=dict(ppu_shadow='00'*32,prepared_source='00'*32,prepared_bg='00'*32)
        rows=[dict(snes_palette=dict(empty)) for _ in range(5)]
        for name,offset in (('ppu_shadow',2),('prepared_source',3),('prepared_bg',4)):
            rows[offset]['snes_palette'][name]=(struct.pack('<16H',*generation['words']).hex()
                if name=='prepared_bg' else '01'*16+'00'*16)
        return rows,generation

    def test_three_stages_are_measured_independently(self):
        rows,generation=self.fixture()
        self.assertEqual(delivery_offsets(rows,generation),dict(ppu_shadow=2,prepared_source=3,prepared_bg=4))

    def test_repeated_rgb_has_no_fabricated_delivery_time(self):
        rows,generation=self.fixture()
        rows[4]['snes_palette']['prepared_bg']='00'*32
        self.assertEqual(delivery_offsets(rows,generation,True),dict(ppu_shadow=2,prepared_source=3,prepared_bg=None))
        with self.assertRaisesRegex(ValueError,'prepared_bg'):delivery_offsets(rows,generation)

    def test_out_of_order_pipeline_rejected(self):
        rows,generation=self.fixture()
        rows[1]['snes_palette']['prepared_bg']=rows[4]['snes_palette']['prepared_bg']
        with self.assertRaisesRegex(ValueError,'out of order'):delivery_offsets(rows,generation)
