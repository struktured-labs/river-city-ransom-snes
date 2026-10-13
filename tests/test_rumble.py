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


class Weapons(unittest.TestCase):
    def setUp(self):
        self.table = rp.weapon_table()

    def test_all_weapons_and_kinds(self):
        self.assertEqual([w for w, *_ in self.table], list(rp.WEAPONS))
        self.assertEqual(sorted(rp.KINDS), list(range(8, 16)))
        self.assertEqual(set(rp.KINDS.values()), set(rp.WEAPONS) - {'FISTS'})

    def test_requested_character(self):
        t = {w: (s, k, f, e) for w, s, k, f, e in self.table}
        self.assertEqual(t['PIPE'][3], 'DECAY')               # sharp hit, then fade
        self.assertEqual(t['CHAIN'][3], 'RATTLE')
        self.assertEqual(t['ROCK'][3], 'FLAT')                # single thud: strong and short
        self.assertGreaterEqual(t['ROCK'][0], 12)
        self.assertLessEqual(t['ROCK'][2], 6)
        self.assertEqual(max(f for *_, f, _ in t.values()), t['TIRE'][2])   # longest ...
        self.assertLessEqual(t['TIRE'][0], 6)                 # ... and soft
        self.assertEqual(min(s for s, *_ in t.values()), t['FISTS'][0])     # light tap
        for w, (s, k, *_ ) in t.items():
            self.assertGreaterEqual(s, k, f'{w}: intensity belongs on the strong motor (DS3 weak is on/off)')

    def test_damage_scales_strength_and_length(self):
        for w in rp.WEAPONS:
            prev = None
            for d in range(0, 40):
                lvl, n, _ = rp.weapon_pulse(w, 'LAND', d)
                cur = (lvl >> 4, n)
                if prev:
                    self.assertGreaterEqual(cur[0], prev[0])
                    self.assertGreaterEqual(cur[1], prev[1])
                prev = cur
                self.assertLessEqual(n, rp.MAX_FRAMES)
            self.assertGreater(rp.weapon_pulse(w, 'LAND', 24)[1], rp.weapon_pulse(w, 'LAND', 0)[1])
            self.assertEqual(rp.weapon_pulse(w, 'LAND', 24), rp.weapon_pulse(w, 'LAND', 99))   # capped

    def test_hits_taken_get_two_more_strong(self):
        for w in rp.WEAPONS:
            for ev in ('TAKE', 'OBJECT'):
                land = rp.weapon_pulse(w, 'LAND', 4)[0] >> 4
                self.assertEqual(rp.weapon_pulse(w, ev, 4)[0] >> 4, min(land + 2, 15))

    def test_knockdown_and_boss_stay_on_top(self):
        p = rp.Pulse()
        p.start('KNOCKDOWN')
        p.frame()
        for ev in ('LAND', 'OBJECT', 'TAKE', 'LAND_KO'):
            self.assertFalse(p.start_weapon(ev, 'PIPE', 99))
        p = rp.Pulse()
        p.start('BOSS')
        self.assertFalse(p.start_weapon('LAND_KO', 'ROCK', 99))
        p = rp.Pulse()
        self.assertTrue(p.start_weapon('LAND', 'TIRE', 0))
        self.assertTrue(p.start('BLOCK') is False)
        self.assertTrue(p.start('KNOCKDOWN'))
        self.assertEqual(p.env, 'FLAT')

    def test_envelopes(self):
        p = rp.Pulse()
        p.start_weapon('LAND', 'PIPE', 0)
        lvl, n, _ = rp.weapon_pulse('PIPE', 'LAND', 0)
        sent = [p.frame() for _ in range(n + 3)]
        strong = [v >> 4 for v in sent[:n]]
        self.assertEqual(strong[0], lvl >> 4)
        self.assertEqual(strong, sorted(strong, reverse=True))
        self.assertLess(strong[-1], strong[0])
        self.assertEqual(sent[n:], [0, 0, None])
        self.assertEqual(sent[:n], rp.envelope(lvl, n, 'DECAY'))
        p = rp.Pulse()
        p.start_weapon('LAND', 'CHAIN', 0)
        lvl, n, _ = rp.weapon_pulse('CHAIN', 'LAND', 0)
        sent = [p.frame() for _ in range(n)]
        self.assertEqual(sent, rp.envelope(lvl, n, 'RATTLE'))
        self.assertGreaterEqual(len({v >> 4 for v in sent}), 2)
        self.assertTrue(all(v & 15 == lvl & 15 for v in sent))

    def test_bad_weapon_table_rejected(self):
        text = rp.ASM.read_text()
        with self.assertRaises(ValueError):
            rp.weapon_table(text.replace('WPN 12, 4,  9, ENV_DECAY', 'WPN 12, 4,  9, ENV_FLAT'))
        with self.assertRaises(ValueError):
            rp.weapon_table(text.replace('.byte WC_ROCK, WC_KNUCKLES', '.byte WC_KNUCKLES, WC_ROCK'))

    def test_no_program_bank_db_in_helpers(self):
        code = '\n'.join(l.split(';')[0] for l in rp.ASM.read_text().splitlines()).lower()
        for op in ('phk', 'plb', 'phb'):
            self.assertNotRegex(code, rf'\b{op}\b')


class Helper(unittest.TestCase):
    def test_assembled_helper_passes_the_builder_checks(self):
        if not (ROOT / '.deps/cc65/bin/ca65').exists():
            self.skipTest('cc65 not installed')
        import os
        with tempfile.TemporaryDirectory() as d:
            cwd = os.getcwd()
            os.chdir(ROOT)
            try:
                helper, parts, names = br.assemble(Path(d))
            finally:
                os.chdir(cwd)
        self.assertEqual(len(helper), br.SIZE)
        self.assertEqual([(a, len(b)) for a, b in parts], list(br.AREAS))
        # weapon tables assembled as the WPN lines say
        tab = dict(parts)[0x6D24]
        at = lambda n: names[n] - 0x6D24
        for i, (w, s, k, f, e) in enumerate(rp.weapon_table()):
            self.assertEqual((tab[at('wpn_strong') + i], tab[at('wpn_weak') + i], tab[at('wpn_frames') + i],
                              tab[at('wpn_env') + i]), (s, k, f, rp.ENVS.index(e)), w)
        self.assertEqual(tab[at('dmg_latch'):at('dmg_latch') + 12].hex(), '48a5078f08f87e6838e50760')
        bad = bytearray(helper)
        i = bad.find(br.WRIO_STORE)
        bad[i - 1] = 0x40                         # a WRIO write with bit 7 low
        with self.assertRaises(ValueError):
            br.helper_checks(bytes(bad), names)


if __name__ == '__main__':
    unittest.main()
