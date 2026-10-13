"""Rumble pulse table and frame timer, as snes/rumble.asm implements them.

The table lives in snes/rumble.asm (the PULSE lines); this module parses it
and models the per-frame step so unit tests and the snes9x check can use
the same rules as the ROM.

Protocol (Limited Run Games "SNES Rumble", MiSTer SNES core rtl/ioport.sv,
Mesen2 SnesRumbleController): after the joypad read, 16 bits MSB first on
port-1 IOBit, each clocked by a $4016 read; $72 then the level byte (high
nibble strong/large motor, low nibble weak/small motor).
"""
import re
from pathlib import Path

ASM = Path(__file__).resolve().parent.parent / 'snes' / 'rumble.asm'
SENTRY = 0x72
MAX_FRAMES = 60
OFF_PACKETS = 2
WEAPONS = ('FISTS', 'STICK', 'PIPE', 'CHAIN', 'KNUCKLES', 'ROCK', 'TIRE', 'BOX', 'CAN')
ENVS = ('FLAT', 'DECAY', 'RATTLE')
# object kind $CB -> weapon (kinds $08-$11; others are fists)
KINDS = {0x08: 'ROCK', 0x09: 'KNUCKLES', 0x0A: 'STICK', 0x0B: 'PIPE', 0x0C: 'CHAIN',
         0x0D: 'TIRE', 0x0E: 'BOX', 0x0F: 'CAN'}
EVENTS = ('NONE', 'BLOCK', 'LAND', 'OBJECT', 'TAKE', 'LAND_KO', 'BOSS', 'KNOCKDOWN')


def pulse_table(text=None):
    """[(event, strong, weak, frames)] in event (= priority) order, from the
    PULSE lines, checked against the pulse_frames bytes."""
    text = ASM.read_text() if text is None else text
    rows = re.findall(r'^\s*PULSE\s+(\d+),\s*(\d+),\s*(\d+)\s*;\s*EV_(\w+)', text, re.M)
    frames = re.search(r'^pulse_frames:\s*\n\s*\.byte\s+([^\n;]+)', text, re.M)
    if not rows or not frames:
        raise ValueError('Pulse table not found')
    fb = [int(v) for v in frames.group(1).split(',')]
    out = []
    for i, (s, w, f, name) in enumerate(rows):
        s, w, f = int(s), int(w), int(f)
        if name != EVENTS[i]:
            raise ValueError(f'Event {i} is {name}, expected {EVENTS[i]}')
        if not (0 <= s <= 15 and 0 <= w <= 15 and 0 <= f <= MAX_FRAMES):
            raise ValueError(f'EV_{name}: motor levels are 0-15, frames 0-{MAX_FRAMES}')
        if fb[i] != f:
            raise ValueError(f'EV_{name}: pulse_frames has {fb[i]}, PULSE line {f}')
        out.append((name, s, w, f))
    if len(fb) != len(out):
        raise ValueError('pulse_frames and PULSE lines differ in length')
    return out


def _const(text, name):
    return int(re.search(rf'^{name}\s*=\s*(\d+)', text, re.M).group(1))


def weapon_consts(text=None):
    text = ASM.read_text() if text is None else text
    return {n: _const(text, n) for n in ('RATTLE_LOW', 'DMG_CAP', 'TAKE_BONUS', 'KO_BONUS', 'KO_MIN_FRAMES')}


def weapon_table(text=None):
    """[(weapon, strong, weak, ticks, envelope)] from the WPN lines, checked
    against the assembled byte rows and the kind_class row."""
    text = ASM.read_text() if text is None else text
    rows = re.findall(r'^\s*WPN\s+(\d+),\s*(\d+),\s*(\d+),\s*ENV_(\w+)\s*;\s*WC_(\w+)', text, re.M)
    if [r[4] for r in rows] != list(WEAPONS):
        raise ValueError('WPN lines are not in WEAPONS order')
    out = [(w, int(s), int(k), int(f), e) for s, k, f, e, w in rows]
    for label, col in (('wpn_weak', 2), ('wpn_frames', 3)):
        m = re.search(rf'^{label}:\s*\n\s*\.byte\s+([^\n;]+)', text, re.M)
        if [int(v) for v in m.group(1).split(',')] != [r[col] for r in out]:
            raise ValueError(f'{label} differs from the WPN lines')
    m = re.search(r'^wpn_env:\s*\n\s*\.byte\s+([^\n;]+)', text, re.M)
    if [int(v) for v in m.group(1).split(',')] != [ENVS.index(r[4]) for r in out]:
        raise ValueError('wpn_env differs from the WPN lines')
    m = re.search(r'^kind_class:.*\n\s*\.byte\s+([^\n;]+)\n\s*\.byte\s+([^\n;]+)', text, re.M)
    cls = [v.strip()[3:] for v in (m.group(1) + ',' + m.group(2)).split(',')]
    if cls[:8] != [KINDS[k] for k in range(8, 16)]:
        raise ValueError('kind_class differs from KINDS')
    for w, s, k, f, e in out:
        if not (0 <= s <= 15 and 0 <= k <= 15 and 0 < f and f + 12 <= MAX_FRAMES):
            raise ValueError(f'WC_{w} out of range')
    return out


def weapon_pulse(weapon, event, damage, table=None, consts=None):
    """(level byte, ticks, envelope) that start_weapon sets."""
    table = table or weapon_table()
    c = consts or weapon_consts()
    w, s, k, f, env = table[WEAPONS.index(weapon)]
    bonus = min(damage, c['DMG_CAP']) // 4
    ticks = f + 2 * bonus
    strong = s + bonus
    if event == 'LAND_KO':
        strong += c['KO_BONUS']
        ticks = max(ticks, c['KO_MIN_FRAMES'])
    elif event != 'LAND':
        strong += c['TAKE_BONUS']
    return level(min(strong, 15), min(k + bonus // 2, 15)), ticks, env


def envelope(lvl, ticks, env, rattle_low=None):
    """Level bytes sent on each tick of a pulse (env_level)."""
    low = weapon_consts()['RATTLE_LOW'] if rattle_low is None else rattle_low
    out = []
    for t in range(ticks - 1, -1, -1):        # timer after the decrement
        if env == 'DECAY':
            out.append(lvl)
            if lvl >= 0x30:
                lvl -= 0x10
        elif env == 'RATTLE' and t & 1:
            out.append((lvl & 0x0F) | (low << 4))
        else:
            out.append(lvl)
    return out


def level(strong, weak):
    return (strong << 4) | weak


def packet_bits(lvl):
    """The 16 IOBit values sent for one packet, MSB first."""
    word = (SENTRY << 8) | lvl
    return [(word >> (15 - i)) & 1 for i in range(16)]


class Pulse:
    """State of rumble_frame / start_pulse."""

    def __init__(self, table=None):
        self.table = table or pulse_table()
        self.timer = self.level = self.rank = self.off = 0
        self.env = 'FLAT'
        self.wt, self.wc = weapon_table(), weapon_consts()

    def start_weapon(self, event, weapon, damage):
        ev = EVENTS.index(event)
        if self.timer and self.timer <= MAX_FRAMES and ev < self.rank:
            return False
        self.level, self.timer, self.env = weapon_pulse(weapon, event, damage, self.wt, self.wc)
        self.rank = ev
        return True

    def start(self, event):
        ev = EVENTS.index(event) if isinstance(event, str) else event
        if ev == 0:
            return False
        if self.timer and self.timer <= MAX_FRAMES and ev < self.rank:
            return False
        _, s, w, f = self.table[ev]
        self.rank, self.timer, self.level = ev, f, level(s, w)
        self.env = 'FLAT'
        return True

    def frame(self, gameplay=True):
        """One falling strobe. Returns the level byte sent, or None."""
        if not gameplay or self.timer > MAX_FRAMES:
            self.timer = self.rank = 0
        elif self.timer:
            self.timer -= 1
            self.off = OFF_PACKETS
            lvl = self.level
            if self.env == 'DECAY' and self.level >= 0x30:
                self.level -= 0x10
            elif self.env == 'RATTLE' and self.timer & 1:
                lvl = (lvl & 0x0F) | (self.wc['RATTLE_LOW'] << 4)
            return lvl if lvl else None
        if self.off:
            if self.off > OFF_PACKETS:
                self.off = 0
                return None
            self.off -= 1
            return 0
        return None
