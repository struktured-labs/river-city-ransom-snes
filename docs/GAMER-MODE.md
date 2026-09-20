# Gamer Mode (locked)

Issue [#21](https://github.com/struktured-labs/river-city-ransom-snes/issues/21).
Original apply is in `tools/nes_difficulty.py` / [#22](https://github.com/struktured-labs/river-city-ransom-snes/issues/22).
Not implemented in a cartridge yet. Novice (`$064C=1`) and Advanced (`$064C=2`) stay byte-identical.

## Play

One mode, two legal ways through it:

1. Stay at original 63/127 and win on execution.
2. Shop past those caps if you want a valve, or if you just want the extra numbers (speed included).

Grinding is optional. It is not the intended-only path.

## Enemies

- Skill RAM **3**, add **+32** (`$B946[3]`, already in the NES table).
- Gamer-only clamps: combat/will **127**, stamina **255**. Saturate; never wrap.
- Original `$B900`/`$B923` stay 63/127 for Novice/Advanced.
- Simon class 22 on Gamer: punch 93, will 95, stamina **150** (Advanced is 63/63/127).
- Street punks get the same +32 on spawn. No accidental weaker bosses.

## Player (Gamer only)

- Start still 15 combat / 63 stam. Food still stacks every eat.
- Caps rise to combat/will/agility **127** and stamina/max power **255**.
- **Speed uses the unmasked agility byte** on Gamer only. NES run/jump does `LDA $04AF,X / AND #$3F` at PRG `$1A316` and `$1A389`; skip that mask in this mode so 64–127 actually moves faster. Table indices that take 4×LSR of agility still clamp so they cannot walk off the table.
- Novice/Advanced keep the `AND #$3F` (original 63 speed ceiling).

## SRAM (SNES QoL)

Original NES has no battery; passwords are 6/7-bit and cannot store Gamer stats past 63/127.

- Battery-backed SRAM on the SNES image (EverDrive / cart save).
- Saves skill, full 8-bit stats, inventory, money, story flags.
- Works for every skill level; required for Gamer once anything exceeds the NES password width.
- Original password screen stays. A password that would drop bits is rejected or not offered for that file, not silently clamped.
- Diagnostic SRAM loggers stay a separate map; do not collide with the game save.

## UI / not this spec

- LEVEL menu: GAMER (or GAMER MODE) as a fourth skill next to Novice/Advanced. Intermediate is [#20](https://github.com/struktured-labs/river-city-ransom-snes/issues/20) (+8, original caps) and must not steal `$064C=2`.
- Stamina HUD currently treats ≥64 as index 63. Gamer bars above 127 need their own scale or they look maxed.
- Present Status already prints hundreds digits.

## Tests when implemented

- Novice/Advanced spawn and `AND #$3F` speed unchanged.
- Gamer Simon stam/will/punch > Advanced; no 8-bit wrap.
- Gamer agility 80 runs faster than 63; Novice/Advanced 80 (if poked) still AND to 63.
- SRAM round-trip of a 80/180 file; password path does not silently truncate.
