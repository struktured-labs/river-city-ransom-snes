"""Original-NES skill-level apply: table, clamps, and Simon class 22.

US PRG CRC 78784CBF. Skill RAM is $064C: 1=Novice (+0), 2=Advanced (+16).
The LEVEL menu never writes 0 or 3, but $B946 still has those slots.
"""
from pathlib import Path

from .rom import Rom

STATS = ('punch', 'kick', 'weapon', 'throw', 'agility', 'defense',
         'strength', 'will', 'stamina')
SKILL_ADD_OFFSET = 0x13946  # $B946 in the spawn bank
CLASS_TABLE_OFFSET = 0x139D6  # $B9D6, 9 bytes per class
COMBAT_CLAMP = 0x3F
STAMINA_CLAMP = 0x7F
SIMON_CLASS = 22
SKILL_NOVICE = 1
SKILL_ADVANCED = 2
SKILL_GAMER = 3
SKILL_ADD = {0: -16, 1: 0, 2: 16, 3: 32}
GAMER_COMBAT_CLAMP = 127
GAMER_STAMINA_CLAMP = 255
# NES run/jump: LDA $04AF,X / AND #$3F (Gamer skips the AND). PRG offsets of the LDA.
AGILITY_SPEED_MASK_OFFSETS = (0x1A316, 0x1A389)


def prg_from(rom_bytes):
    rom = Rom.parse(rom_bytes)
    rom.require_rcr_us()
    return rom.prg


def agility_speed_masks(prg):
    """Return (offset, bytes) for each LDA $04AF,X / AND #$3F speed site."""
    expected = b'\xbd\xaf\x04\x29\x3f'
    rows = []
    for offset in AGILITY_SPEED_MASK_OFFSETS:
        got = bytes(prg[offset:offset + 5])
        if got != expected:
            raise ValueError(f'Agility speed mask missing at ${offset:05X}')
        rows.append((offset, got))
    return tuple(rows)


def skill_add_table(prg):
    raw = prg[SKILL_ADD_OFFSET:SKILL_ADD_OFFSET + 4]
    return tuple(b if b < 128 else b - 256 for b in raw)


def class_stats(prg, index):
    base = CLASS_TABLE_OFFSET + index * 9
    rec = prg[base:base + 9]
    if len(rec) != 9:
        raise ValueError('Missing class row')
    return dict(zip(STATS, rec))


def apply_boss(base, skill, stamina=False):
    """$B900 (combat/will, cap 63) or $B923 (stamina, cap 127) for type >= 9."""
    added = base + SKILL_ADD[skill]
    cap = STAMINA_CLAMP if stamina else COMBAT_CLAMP
    if added <= 0:
        return 1
    if added >= cap + 1:
        return cap
    return added


def apply_gamer(base, stamina=False):
    """Locked #21 apply: +32 with 127/255 caps. Original $B900/$B923 stay 63/127."""
    added = base + SKILL_ADD[SKILL_GAMER]
    cap = GAMER_STAMINA_CLAMP if stamina else GAMER_COMBAT_CLAMP
    if added <= 0:
        return 1
    if added >= cap + 1:
        return cap
    return added


def simon_spawn(prg, skill):
    base = class_stats(prg, SIMON_CLASS)
    return {name: apply_boss(base[name], skill, stamina=(name == 'stamina'))
            for name in STATS}, base


def simon_gamer(prg):
    base = class_stats(prg, SIMON_CLASS)
    return {name: apply_gamer(base[name], stamina=(name == 'stamina'))
            for name in STATS}, base


def wrap_hypothesis(novice_stamina=118):
    doubled = novice_stamina * 2
    return dict(doubled=doubled, wrapped8=doubled & 0xFF, masked7=doubled & 0x7F)


def planned_skill_levels():
    """Hook map for #20/#21. Original $064C=1/2 must stay Novice/Advanced.

    $B946 is F0 00 10 20 (-16, 0, +16, +32). The LEVEL menu INC/DEC only
    allows 1 and 2, so slots 0 and 3 are unused original bytes, not extra
    modes. Intermediate cannot reuse 2. Gamer as index 3 (+32) still clamps
    Simon stamina at 127, same as Advanced, and will stays 63.
    """
    return (
        dict(name='Novice', ram=1, add=0, original=True),
        dict(name='Intermediate', ram=None, add=8, original=False,
             note='Needs a new $064C value and table byte; between +0 and +16.'),
        dict(name='Advanced', ram=2, add=16, original=True),
        dict(name='Gamer Mode', ram=3, add=32, original=False,
             combat_cap=127, stamina_cap=255, player_cap_combat=127,
             player_cap_stamina=255, unmask_agility_speed=True,
             note='docs/GAMER-MODE.md: optional grind, SRAM, Gamer-only speed>63.'),
    )
