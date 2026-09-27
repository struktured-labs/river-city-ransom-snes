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

    def start(self, event):
        ev = EVENTS.index(event) if isinstance(event, str) else event
        if ev == 0:
            return False
        if self.timer and self.timer <= MAX_FRAMES and ev < self.rank:
            return False
        _, s, w, f = self.table[ev]
        self.rank, self.timer, self.level = ev, f, level(s, w)
        return True

    def frame(self, gameplay=True):
        """One falling strobe. Returns the level byte sent, or None."""
        if not gameplay or self.timer > MAX_FRAMES:
            self.timer = self.rank = 0
        elif self.timer:
            self.timer -= 1
            self.off = OFF_PACKETS
            return self.level if self.level else None
        if self.off:
            if self.off > OFF_PACKETS:
                self.off = 0
                return None
            self.off -= 1
            return 0
        return None
