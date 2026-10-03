import hashlib
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
HAVE = ((ROOT / '.deps/project-nested/Assembly/Project/Spc700/Spc.asm').exists()
        and (ROOT / 'build/gamer-stam-cap-4302/native-cpu.sfc').exists())
ENGINE_SHA = 'f05ff5d4ec083e8768d82fb56e1946f96fb5d102bb245cd7bab237edf34f9b64'


class HookTableTests(unittest.TestCase):
    def test_hooks_cover_the_4302_extensions(self):
        from tools.build_nested_ext import HOOKS, NOISE_TABLE
        text = ' '.join(r for r, _, _ in HOOKS)
        for word in ('sweep driver', 'timed receiver', 'release envelope', 'attack envelope',
                     'publisher owns the volume', 'key-on deferred', 'timer 0'):
            self.assertIn(word, text)
        self.assertEqual(NOISE_TABLE.hex(), '3f3f3f3f3f3e3e3d3c3b3a383735322f')

    def test_hook_matcher_is_exact(self):
        from tools.build_nested_ext import apply_hooks
        with self.assertRaises(ValueError):
            apply_hooks('next_xfer:\n mov 0xF4,#0x7D\n')


@unittest.skipUnless(HAVE, 'needs .deps/project-nested and build 4302')
class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.build_nested_ext import build_engine
        cls.r = build_engine()

    def test_pinned_engine(self):
        self.assertEqual(hashlib.sha256(self.r['engine']).hexdigest(), ENGINE_SHA)

    def test_layout(self):
        r = self.r
        self.assertGreaterEqual(r['base'], 0x400 + r['pn_bytes'])
        self.assertEqual(len(r['engine']), r['base'] - 0x400 + 0x3736 - 0x2F29)
        self.assertNotEqual((len(r['engine']) + 2) & 255, 0x7D)

    def test_driver_calls_project_nested_routines(self):
        from tools.build_nested_ext import BLOCK, decode_block, EXTERNAL, BLOCK_PATCHES
        patched = {a for pc, before, _, _ in BLOCK_PATCHES for a in range(pc, pc + len(before) // 2)}
        r, e = self.r, self.r['engine']
        lo, hi = BLOCK
        base, L = r['base'], r['labels']
        targets = set()
        for pc, (size, mn, ops) in decode_block(self._e4302()).items():
            if mn in ('CALL', 'JMP') and pc not in patched:
                at = base + pc - lo - 0x400
                if any(k == 'abs' for k, _, _ in ops):
                    targets.add(e[at + 1] | e[at + 2] << 8)
        for t in targets:
            self.assertTrue(base <= t < base + hi - lo or t in {L[v] for v in EXTERNAL.values()}
                            or t in (L['rcr_dutycmp0'], L['rcr_dutycmp1'], L['rcr_variant0'], L['rcr_variant1']),
                            hex(t))
        self.assertIn(L['check_timer3'], targets)
        self.assertIn(L['square0'], targets)

    def _e4302(self):
        m = self.r['meta']
        at, n = m['sweep_driver_rom_offset'], 13110
        return self.r['rom'][at:at + n]

    def test_noise_table_in_image(self):
        at = self.r['labels']['noise_freq_table'] - 0x400
        self.assertEqual(self.r['engine'][at:at + 16].hex(), '3f3f3f3f3f3e3e3d3c3b3a383735322f')

    def test_no_dmc_and_no_triangle_keyon(self):
        src = self.r['patched_source'].lower()
        self.assertNotIn('call !update_dmc', src.replace(' ', ''))
        self.assertNotIn('!0xbfff', src.replace(' ', ''))


if __name__ == '__main__':
    unittest.main()
