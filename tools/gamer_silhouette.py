"""True-silhouette outline pixels for the Gamer red goon outline.

A sprite tile is shared by many metasprites, so whether an outline pixel on a
tile border is on the outer silhouette depends on what the metasprite puts
next to it. This module replays the game's metasprite interpreter (fixed bank
$ED0E-$EF84) over every human animation frame (sprite kinds 0-7, NES bank 3
$8000 tables), every head type, and both branches of the held-object opcode,
and composes each frame from the CHR banks that can be in the sprite windows
during street play. An outline pixel (color 1) of a physical CHR tile is on
the silhouette when, in EVERY composition that uses that tile and under every
bank assignment, one of its 4-neighbours is transparent: outside the tile and
not covered by another sprite of the same metasprite, or inside the tile and
both transparent and not covered. Pixels that are outer in some frames and
inside in others stay dark (no red inside the body is the stronger rule).

Held-object parts (the $FC branch: a carried goon or a weapon) form their own
composition; the holder's sprites are not the held actor's body.
"""
import itertools

# SNES image banks: bank 4 holds NES PRG bank 3 at $8000 and a copy of the
# fixed bank at $C000; bank 5 holds NES PRG bank 4.
ANIM_BANK = 4
HEAD_BANK = 5
KIND_TABLE = 0x8000          # NES bank 3: frame table pointer per sprite kind
KIND_COUNT = 39
HUMAN_KINDS = range(0, 8)    # $00CB,slot 0-7: human animation sets
HEAD_TILES = 0xEF99          # 8 head tiles ($60-$67) x 5 head types
HEAD_TYPES = 5
HELD_TYPES = 5               # $03B0 mod 5 picks the held object's frame
GANG_HEADS = 0xB7D1          # NES bank 4: head CHR bank per gang class (18)
BOSS_HEADS = 0xB7E3          # NES bank 4: (window 1, window 2) per boss (7)
# 1 KB CHR banks in the four sprite windows ($0521-$0524) during street play:
# body banks $40 and $41 fixed, heads per gang/boss in windows 1 and 2.
BODY_WINDOWS = {0: 0x40, 3: 0x41}
DEFAULT_HEADS = {1: 0x42, 2: 0x45}
OUTLINE, TRANSPARENT = 1, 0
MAX_STEPS = 60
MAX_COUNT = 40


class Rom:
    def __init__(self, image, chr_tiles):
        self.image = image
        self.chr = chr_tiles         # callable: physical tile -> 8x8 indices

    def byte(self, a, bank=ANIM_BANK):
        if not 0x8000 <= a <= 0xFFFF:
            raise ValueError(f'address {a:#x} outside PRG')
        return self.image[bank * 65536 + a]

    def word(self, a, bank=ANIM_BANK):
        return self.byte(a, bank) | self.byte(a + 1, bank) << 8


def sbyte(v):
    return v - 256 if v > 127 else v


def window_banks(rom):
    gang = [rom.byte(GANG_HEADS + i, HEAD_BANK) for i in range(18)]
    boss = [(rom.byte(BOSS_HEADS + 2 * i, HEAD_BANK), rom.byte(BOSS_HEADS + 2 * i + 1, HEAD_BANK))
            for i in range(7)]
    banks = {w: {b} for w, b in BODY_WINDOWS.items()}
    banks[1] = {DEFAULT_HEADS[1], *gang, *(p[0] for p in boss)}
    banks[2] = {DEFAULT_HEADS[2], *gang, *(p[1] for p in boss)}
    return {w: sorted(v) for w, v in banks.items()}


def frame_count(rom, kind):
    starts = sorted({rom.word(KIND_TABLE + 2 * k) for k in range(KIND_COUNT)})
    s = rom.word(KIND_TABLE + 2 * kind)
    nxt = min([x for x in starts if x > s] + [s + 256])
    n = min(128, (nxt - s) // 2)
    for f in range(n):
        if not 0x8000 <= rom.word(s + 2 * f) < 0xC000:
            return f
    return n


def run_script(rom, ptr, kind, head, holding, held_type):
    """Sprites (tile, x, y, attr) drawn by one frame script, split into the
    actor's own body and the held-object part. Mirrors $ED87-$EF81."""
    parts = {'body': [], 'held': []}
    cur = 'body'
    c, y13, r12, ret, a07, lst = ptr, 0, 0, None, 0, 0
    for _ in range(MAX_STEPS):
        y = y13
        x = rom.byte(c + y)
        if x == 0:
            return parts
        if x == 0xFF:                       # draw the descriptor at ptr, then continue
            ret, r12 = c, y + 3
            c, y13 = rom.byte(c + y + 1) | rom.byte(c + y + 2) << 8, 0
            continue
        if x in (0xFE, 0xFD):               # count + per-sprite attribute list
            y += 1
            cnt = rom.byte(c + y)
            y += 1
            if x == 0xFE:
                lst = rom.word(c + y)
                y += 2
            else:                           # list chosen by head type (max 2)
                c += y
                lst = rom.word(c + 2 * min(head, 2) + 2)
                c, y = rom.word(c), 0
        elif x == 0xFC:                     # held object
            y += 1
            if holding:
                c += y
                ret, r12 = rom.word(c), 0x80
                c, y13, cur = rom.word(c + 2 + 2 * held_type), 0, 'held'
            else:
                c, y13 = rom.word(c + y), 0
            continue
        else:
            cnt, a07 = x, rom.byte(c + y + 1)
            y += 2
        tiles, offs = rom.word(c + y), rom.word(c + y + 2)
        y13 = y + 4
        if cnt > MAX_COUNT:
            raise ValueError('sprite count')
        for j in range(cnt):
            attr = a07 if a07 < 0x80 else 0
            t = rom.byte(tiles + j)
            if 0x60 <= t < 0x68 and kind < 8:
                t = rom.byte(HEAD_TILES + (t - 0x60) * 5 + head)
            if lst >> 8:
                attr = rom.byte(lst + j)
            parts[cur].append((t, sbyte(rom.byte(offs + 2 * j)), -sbyte(rom.byte(offs + 2 * j + 1)), attr))
        if r12:
            y13, c, r12, cur = r12 & 0x7F, ret, 0, 'body'
    raise ValueError('script does not end')


def compositions(rom):
    out = set()
    for kind in HUMAN_KINDS:
        table = rom.word(KIND_TABLE + 2 * kind)
        for f in range(frame_count(rom, kind)):
            ptr = rom.word(table + 2 * f)
            for head in range(HEAD_TYPES):
                for holding in (0, 1):
                    for held in (range(HELD_TYPES) if holding else (0,)):
                        for sprites in run_script(rom, ptr, kind, head, holding, held).values():
                            if sprites:
                                out.add(tuple(sprites))
    return sorted(out)


def placed(px, attr, r, c):
    if attr & 0x40:
        c = 7 - c
    if attr & 0x80:
        r = 7 - r
    return px[r][c]


def silhouette(comps, banks, chr_px):
    """{(physical tile, row, col): outer in every use} for outline pixels of
    every physical tile used by the compositions."""
    outer = {}
    for sprites in comps:
        windows = sorted({t >> 6 for t, _, _, _ in sprites})
        for combo in itertools.product(*(banks[w] for w in windows)):
            bank = dict(zip(windows, combo))
            placed_tiles, cover = [], set()
            for t, dx, dy, attr in sprites:
                phys = bank[t >> 6] * 64 + (t & 63)
                px = chr_px(phys)
                placed_tiles.append((phys, px, dx, dy, attr))
                for r in range(8):
                    for c in range(8):
                        if placed(px, attr, r, c) != TRANSPARENT:
                            cover.add((dx + c, dy + r))
            for phys, px, dx, dy, attr in placed_tiles:
                for r in range(8):
                    for c in range(8):
                        if placed(px, attr, r, c) != OUTLINE:
                            continue
                        o = any((dx + cc, dy + rr) not in cover
                                for rr, cc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)))
                        key = (phys, 7 - r if attr & 0x80 else r, 7 - c if attr & 0x40 else c)
                        outer[key] = outer.get(key, True) and o
    return outer
