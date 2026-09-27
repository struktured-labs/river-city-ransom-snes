import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools import rumble_pulses as rp
from tools import build_rumble as br

ROOT = Path(__file__).resolve().parent.parent


class PulseTable(unittest.TestCase):
    def setUp(self):
        self.table = rp.pulse_table()

    def test_events_match_the_asm_constants(self):
        asm = rp.ASM.read_text()
        consts = {m.group(1): int(m.group(2)) for m in re.finditer(r'^EV_(\w+)\s*=\s*(\d+)', asm, re.M)}
        for i, name in enumerate(rp.EVENTS):
            self.assertEqual(consts[name], i)
        self.assertEqual(consts['COUNT'], len(rp.EVENTS))
        self.assertEqual([e for e, *_ in self.table], list(rp.EVENTS))

    def test_levels_and_frames_in_range(self):
        for name, s, w, f in self.table[1:]:
            self.assertTrue(0 <= s <= 15 and 0 <= w <= 15, name)
            self.assertTrue(0 < f <= rp.MAX_FRAMES, name)
            self.assertTrue(s or w, f'{name} would send level 0')
        self.assertEqual(self.table[0][1:], (0, 0, 0))

    def test_requested_shape(self):
        t = {e: (s, w, f) for e, s, w, f in self.table}
        light = lambda e: t[e][0] + t[e][1]
        # landing a hit: short and light; taking one: medium; knockdown / boss: long and strong
        self.assertLess(light('LAND'), light('TAKE'))
        self.assertLess(t['LAND'][2], t['TAKE'][2])
        for e in ('KNOCKDOWN', 'BOSS'):
            self.assertGreater(light(e), light('TAKE'))
            self.assertGreater(t[e][2], t['TAKE'][2])
            self.assertEqual(t[e][0], 15)
        self.assertLessEqual(light('OBJECT'), light('TAKE'))

    def test_priority_order_is_strength_order(self):
        strength = [s + w for _, s, w, _ in self.table]
        self.assertEqual(strength, sorted(strength))

    def test_bad_table_rejected(self):
        text = rp.ASM.read_text().replace('PULSE  0,  6,  4     ; EV_LAND', 'PULSE  0, 16,  4     ; EV_LAND')
        with self.assertRaises(ValueError):
            rp.pulse_table(text)
        text = rp.ASM.read_text().replace('.byte  0,  3,  4,', '.byte  0,  3,  5,')
        with self.assertRaises(ValueError):
            rp.pulse_table(text)

    def test_packet_bits(self):
        bits = rp.packet_bits(0xCA)
        self.assertEqual(len(bits), 16)
        self.assertEqual(int(''.join(map(str, bits)), 2), 0x72CA)


class Timer(unittest.TestCase):
    def run_pulse(self, event, frames=80, gameplay=lambda i: True):
        p = rp.Pulse()
        p.start(event)
        return [p.frame(gameplay(i)) for i in range(frames)], p

    def test_pulse_length_level_and_off_packets(self):
        for name, s, w, f in rp.pulse_table()[1:]:
            sent, p = self.run_pulse(name)
            self.assertEqual(sent[:f], [rp.level(s, w)] * f, name)
            self.assertEqual(sent[f:f + rp.OFF_PACKETS], [0] * rp.OFF_PACKETS, name)
            self.assertTrue(all(v is None for v in sent[f + rp.OFF_PACKETS:]), name)
            self.assertEqual((p.timer, p.off), (0, 0))

    def test_always_returns_to_zero_core_and_mesen(self):
        # core semantics: a frame with no packet is level 0; Mesen keeps the last packet
        p = rp.Pulse()
        import random
        rnd = random.Random(7)
        mesen = 0
        for i in range(5000):
            if rnd.random() < 0.08:
                p.start(rnd.randrange(1, len(rp.EVENTS)))
            gp = rnd.random() > 0.05
            v = p.frame(gp)
            if v is not None:
                mesen = v
        for i in range(rp.MAX_FRAMES + rp.OFF_PACKETS + 1):
            v = p.frame(True)
            if v is not None:
                mesen = v
        self.assertEqual(mesen, 0)
        self.assertIsNone(p.frame(True))

    def test_pause_silences_at_once(self):
        sent, p = self.run_pulse('KNOCKDOWN', 10, lambda i: i < 3)
        f = rp.pulse_table()[7]
        lvl = rp.level(f[1], f[2])
        self.assertEqual(sent[:3], [lvl] * 3)
        self.assertEqual(sent[3:5], [0, 0])
        self.assertTrue(all(v is None for v in sent[5:]))
        self.assertEqual(p.timer, 0)

    def test_priority(self):
        p = rp.Pulse()
        p.start('KNOCKDOWN')
        p.frame()
        self.assertFalse(p.start('LAND'))
        self.assertTrue(p.start('KNOCKDOWN'))       # same event restarts
        self.assertEqual(p.timer, rp.pulse_table()[7][3])
        p = rp.Pulse()
        p.start('LAND')
        self.assertTrue(p.start('TAKE'))
        for _ in range(20):
            p.frame()
        self.assertTrue(p.start('LAND'))             # nothing running any more

    def test_power_on_garbage_is_cleared(self):
        p = rp.Pulse()
        p.timer, p.level, p.off = 200, 0xFF, 9
        self.assertIsNone(p.frame(True))
        self.assertEqual((p.timer, p.off), (0, 0))
        self.assertIsNone(p.frame(True))


class Helper(unittest.TestCase):
    def test_assembled_helper_passes_the_builder_checks(self):
        ca65, ld65 = ROOT / '.deps/cc65/bin/ca65', ROOT / '.deps/cc65/bin/ld65'
        if not ca65.exists():
            self.skipTest('cc65 not installed')
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            subprocess.run([str(ca65), '-o', str(d / 'r.o'), str(ROOT / 'snes/rumble.asm')], check=True)
            subprocess.run([str(ld65), '-C', str(ROOT / 'snes/rumble.cfg'), '-Ln', str(d / 'r.lbl'),
                            '-o', str(d / 'r.bin'), str(d / 'r.o')], check=True)
            helper = (d / 'r.bin').read_bytes()
            names = {}
            for line in (d / 'r.lbl').read_text().splitlines():
                parts = line.split()
                if len(parts) >= 3 and parts[2].startswith('.'):
                    names[parts[2][1:]] = int(parts[1], 16)
        self.assertEqual(len(helper), br.SIZE)
        br.helper_checks(helper, names)
        bad = bytearray(helper)
        i = bad.find(br.WRIO_STORE)
        bad[i - 1] = 0x40                         # a WRIO write with bit 7 low
        with self.assertRaises(ValueError):
            br.helper_checks(bytes(bad), names)


if __name__ == '__main__':
    unittest.main()
