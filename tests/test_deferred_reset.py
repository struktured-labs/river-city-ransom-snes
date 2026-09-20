import unittest
from pathlib import Path
from tools.prepare_audio import paired_engine


class DeferredResetTests(unittest.TestCase):
    def source(self):
        return (Path(__file__).resolve().parents[1]/'.deps/upernes/source/asm/Memblers_2a03.bin').read_bytes()

    def test_requires_reset_mode(self):
        with self.assertRaises(ValueError):
            paired_engine(self.source(), deferred_reset=True)

    def test_game_builder_exposes_deferred_reset_without_aliasing_fast_reset(self):
        source = (Path(__file__).resolve().parents[1]/'tools/build_native.py').read_text()
        self.assertIn("parser.add_argument('--experimental-deferred-reset-audio'", source)
        self.assertIn('paired_engine(engine.read_bytes(), reset_notes=True, deferred_reset=True)', source)
        self.assertIn("defines += ['-D', 'AUDIO_DEFERRED_RESET=1']", source)
        self.assertIn('"experimental_deferred_reset_audio": experimental_deferred_reset_audio', source)

    def test_only_checked_original_sites_change(self):
        source = self.source()
        engine = paired_engine(source, reset_notes=True, deferred_reset=True)
        allowed = {0x28e, *range(0x87, 0x8a), *range(0xbf, 0xc5),
                   *range(0x1a1, 0x1a7), *range(0x33a, 0x33d)}
        self.assertEqual(len(engine), 0x2c38)
        self.assertTrue(all(i in allowed for i, (a,b) in enumerate(zip(source,engine)) if a!=b))
        self.assertEqual(engine[0xbf:0xc5], bytes.fromhex('180154000000'))
        self.assertEqual(engine[0x1a1:0x1a7], bytes.fromhex('180254000000'))
        self.assertEqual(engine[0x33a:0x33d], bytes.fromhex('5f2a30'))

    def test_default_pair_keeps_legacy_duty_sites(self):
        source = self.source()
        paired = paired_engine(source)
        self.assertEqual(len(paired), 0x2c1f)
        for begin,end in ((0xbf,0xc5),(0x1a1,0x1a7),(0x33a,0x33d)):
            self.assertEqual(paired[begin:end], source[begin:end])
