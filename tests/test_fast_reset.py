import unittest
from pathlib import Path

from tools.prepare_audio import _fast_reset_handler, paired_engine


class FastResetTests(unittest.TestCase):
    def source(self):
        return (Path(__file__).resolve().parents[1] /
                '.deps/upernes/source/asm/Memblers_2a03.bin').read_bytes()

    def test_requires_standalone_reset_mode(self):
        for options in ({'fast_reset': True},
                        {'reset_notes': True, 'deferred_reset': True, 'fast_reset': True},
                        {'reset_notes': True, 'sentinel_reset': True, 'fast_reset': True}):
            with self.assertRaises(ValueError):
                paired_engine(self.source(), **options)

    def test_checked_sites_and_handler_targets(self):
        source = self.source()
        engine = paired_engine(source, reset_notes=True, fast_reset=True)
        handler, labels = _fast_reset_handler()
        self.assertEqual(len(handler), 96)
        self.assertEqual(len(engine), 0x2c7f)
        self.assertNotEqual((len(engine)-1) & 0xff, 0x7d)
        self.assertEqual(engine[0x2c1f:], handler)
        self.assertEqual(handler[:9], bytes.fromhex('0356062356035f9604'))
        for offset, name in ((0xbf, 'duty0'), (0x1a1, 'duty1')):
            target = 0x301f + labels[name]
            self.assertEqual(engine[offset:offset+6],
                             bytes((0x3f, target & 255, target >> 8, 0, 0, 0)))

    def test_native_packet_slot_used_as_zero_dma_hole(self):
        root = Path(__file__).resolve().parents[1]
        runtime = (root/'snes/native_runtime.asm').read_text()
        console = runtime.split('console_write:', 1)[1].split('@joy:', 1)[0]
        self.assertLess(console.index('cmp #$14'), console.index('sta a:$0A00,x'))
        self.assertLess(console.index('jmp @dma'), console.index('sta a:$0A00,x'))
        boot = (root/'snes/native_boot.asm').read_text()
        self.assertLess(boot.index('clear_wram_dma'), boot.index('jsr spc_upload'))

    def test_default_pair_keeps_legacy_duty_sites(self):
        source = self.source()
        paired = paired_engine(source)
        self.assertEqual(paired[0xbf:0xc5], source[0xbf:0xc5])
        self.assertEqual(paired[0x1a1:0x1a7], source[0x1a1:0x1a7])
