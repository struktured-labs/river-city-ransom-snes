import unittest
from pathlib import Path
from tools.prepare_audio import prepare_engine, paired_engine, triangle_dac_release_engine


class PrepareAudioTests(unittest.TestCase):
    def test_in_place_triangle_release_preserves_upload_and_sample(self):
        source = Path('.deps/upernes/source/asm/Memblers_2a03.bin').read_bytes()
        engine = paired_engine(source,reset_notes=True,fast_reset=True)
        result = triangle_dac_release_engine(engine,attack=True,in_place=True)
        self.assertEqual(len(result),len(engine))
        self.assertEqual(result[0x2ae1:0x2b29],engine[0x2ae1:0x2b29])
        self.assertEqual(result[0x2c00:],engine[0x2c00:])
        self.assertEqual(int.from_bytes(result[0x559:0x55b],'little'),0x2f40)
        for offset in (0x838,0x2ae1,0x2b20,0x2b40,0x2bff):
            changed=bytearray(engine);changed[offset]^=1
            with self.assertRaisesRegex(ValueError,'padding'):
                triangle_dac_release_engine(changed,attack=True,in_place=True)

    def test_triangle_attack_is_explicit_mono_only_experiment(self):
        engine = prepare_engine(Path('.deps/upernes/source/asm/Memblers_2a03.bin').read_bytes())
        plain = triangle_dac_release_engine(engine)
        attack = triangle_dac_release_engine(engine, attack=True)
        self.assertEqual(len(plain),len(attack))
        self.assertEqual((plain[0x28a],plain[0x290]),(127,127))
        self.assertEqual((attack[0x28a],attack[0x290]),(31,31))
        self.assertIn(bytes.fromhex('8f27f28fdff33f53076f'),attack[len(engine):])

    def test_triangle_release_is_opt_in_and_preserves_existing_image(self):
        source = Path('.deps/upernes/source/asm/Memblers_2a03.bin').read_bytes()
        engine = paired_engine(source, reset_notes=True, fast_reset=True)
        patched = triangle_dac_release_engine(engine)
        changed = {i for i, (a,b) in enumerate(zip(engine,patched)) if a != b}
        self.assertTrue(changed <= set(range(0x24c,0x24f)) | set(range(0x2a7,0x2aa)) | set(range(0x558,0x564)))
        self.assertEqual(patched[0x24c], 0x5f)
        self.assertEqual(patched[0x2a7], 0x3f)
        self.assertEqual(int.from_bytes(patched[0x559:0x55b], 'little'), 0x400+len(engine))
        self.assertIn(bytes.fromhex('8f27f28f1ff33f53076f'), patched[len(engine):])
        self.assertNotEqual((len(patched)-1)&255, 0x7d)
        self.assertEqual(paired_engine(source, reset_notes=True, fast_reset=True), engine)

    def test_triangle_release_rejects_changed_preimages_and_double_patch(self):
        engine = prepare_engine(Path('.deps/upernes/source/asm/Memblers_2a03.bin').read_bytes())
        for offset in (0x24c, 0x254, 0x2a7, 0x28e, 0x558, 0x567):
            changed = bytearray(engine)
            changed[offset] ^= 1
            with self.assertRaises(ValueError):
                triangle_dac_release_engine(changed)
        with self.assertRaises(ValueError):
            triangle_dac_release_engine(triangle_dac_release_engine(engine))

    def test_unknown_engine_rejected(self):
        with self.assertRaises(ValueError):
            prepare_engine(bytes(0x2c00))

    def test_pinned_patch_changes_only_address_operand(self):
        path = Path('.deps/upernes/source/asm/Memblers_2a03.bin')
        if not path.exists():
            self.skipTest('Pinned dependency not installed')
        original = path.read_bytes()
        patched = prepare_engine(original)
        self.assertEqual(len(patched), len(original))
        self.assertEqual([i for i, (a, b) in enumerate(zip(original, patched)) if a != b], [0x28e])
        self.assertEqual(patched[0x28e], 0xf2)
        with self.assertRaises(ValueError):
            prepare_engine(patched)
