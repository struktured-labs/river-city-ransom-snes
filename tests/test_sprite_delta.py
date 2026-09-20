import unittest

from tools.check_sprite_delta import cases, expected


class SpriteDeltaOracleTests(unittest.TestCase):
    def test_all_attributes_in_both_pattern_halves(self):
        samples=cases()
        for half in (0,8):
            attrs={c['raw'][i] for c in samples if c['half']==half for i in range(2,256,4)}
            self.assertEqual(attrs,set(range(256)))

    def test_single_byte_changes_and_clean_half_invalidation_present(self):
        samples=cases()
        changes=[(a,b) for a,b in zip(samples,samples[1:]) if b['name'].startswith('change-byte-')]
        self.assertEqual(len(changes),6)
        for a,b in changes:
            self.assertEqual(sum(x!=y for x,y in zip(a['raw'],b['raw'])),1)
        a,b=samples[-3:-1]
        self.assertEqual(a['raw'],b['raw'])
        self.assertNotEqual(a['half'],b['half'])
        self.assertEqual(b['dirty'],0)

    def test_all_y_and_tile_values_executed_in_both_halves(self):
        for half in (0,8):
            samples=[c for c in cases() if c['half']==half]
            for offset in (0,1):
                self.assertEqual({c['raw'][i] for c in samples for i in range(offset,256,4)},set(range(256)))

    def test_output_boundary_and_hidden_oam(self):
        raw=bytearray(256)
        raw[:4]=bytes((238,99,0xc3,255))
        raw[-4:]=bytes((239,1,0x20,0))
        result=expected(raw,8)
        self.assertEqual(result[:4],bytes((255,240,99,0xf7)))
        self.assertEqual(result[252:256],bytes((0,240,1,1)))
        self.assertEqual(result[256:512],bytes((0,240,0,0))*64)
        self.assertEqual(result[512:],bytes(32))
