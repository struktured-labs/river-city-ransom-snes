# Rumble (port-1 pad, MiSTer SNES core) — build 4294

## Protocol
Limited Run Games "SNES Rumble" (github.com/LimitedRunGames-Tech/snes-rumble,
`source/player.a`): after the joypad read, 16 bits MSB first on port-1 IOBit
(WRIO `$4201` bit 6), each bit written and then clocked by one `$4016` read.
Byte 1 is the sentry `$72`; byte 2 is the level: high nibble = large/strong
motor, low nibble = small/weak motor, 0-15 each.

## MiSTer path
- SNES_MiSTer `rtl/ioport.sv` (commit 13bf006 "Rumble Support (#419)",
  2025-07-22; first release SNES_20260325, also in SNES_20260603): shifts
  `PORT_P6` (= WRIO bit 6, `rtl/SNES.vhd` `JOY1_P6 <= JPIO67(6)`) on every
  port-1 clock while the latch is low; when the top byte is `$72` it sets
  `JOYSTICK1_RUMBLE` = {hi nibble twice, lo nibble twice}. Every latch
  falling edge clears it, so the level must be resent each frame. Port 1 only.
- `SNES.sv`: `joystick_0_rumble` = `status[8] ? 0 : joystick1_rumble`
  (status[8] = OSD "SNAC"), served by `hps_io` at `UIO_GET_RUMBLE` (`'h3F`).
- Main_MiSTer `input.cpp`: the input loop polls `UIO_GET_RUMBLE` per player
  (outside the OSD menu) and `set_rumble` sends Linux `FF_RUMBLE`
  strong/weak magnitudes to the player's pad if it reports FF_RUMBLE.
  `MiSTer.ini` `rumble=1` is the default (`cfg.cpp`); a hotkey toggles it.

## ROM side
`snes/rumble.asm` at `$6B00` in banks 1-8 (built by `tools/build_rumble.py`):
- frame step: `@joy_done` (`jmp done`, `$244C`) goes through `rumble_frame`,
  in the main loop right after the game's own pad read (never in the NMI).
  While a pulse runs it sends `$72,level` once per game tick; then two
  `$72,$00` off packets (for emulators that keep the last level); otherwise
  nothing. Paused (`$3F`), settings/text (`$0006 = 5`), shops (`$CC`) or a
  non-gameplay screen (`$0100 & $C0 != $C0`) cancel the pulse at once.
- events: bank 5 `$8DD5` (every hit that dealt or blocked a blow) and `$8D10`
  (hit on a goon already lying down) call `rumble_hit` / `rumble_down`.
- pulse table: the `PULSE` lines in `snes/rumble.asm` (strong, weak, game
  ticks; a tick is 1/30 s on the street, where RCR runs its loop every
  second NMI). A new pulse replaces the running one when its event number is
  at least as high.
- RAM `$7EF800-$7EF807` (cleared by the game's boot; power-on garbage is
  rejected by range checks).
- safety: WRIO bit 7 (port-2 IOBit / PPU counter latch) is 1 at every write
  and WRIO is left at `$FF`. A standard pad has no pin-6 line, so on a real
  SNES without a rumble pad the extra writes and `$4016` reads change nothing.
  Always on; no detection or option.
- DB: the pulse tables are read with long addressing (bank `$C1` copy).
  Build 4294 used `PHB/PHK/PLB` there; an NMI or raster IRQ inside that
  window ran with DB on a program bank and froze the game. Fixed in 4295,
  see `docs/FREEZE-FIX.md`.

## Checks
- `tools/mesen/rumble.lua`: bus decoder with MiSTer-core and Mesen2
  semantics; independent hit classifier; R1-R6.
- `python3 -m tools.rumble_snes9x ROM OUT`: RAM-state check S1-S4.
- `python3 -m unittest tests.test_rumble`: table and timer model
  (`tools/rumble_pulses.py`).

## Per-weapon, damage-scaled pulses (trial 4305d)
Build: `python3 -m tools.build_weapon_rumble --parent build/trial-gamer-downshift-4305c/native-cpu.sfc --out build/trial-weapon-rumble-4305d`.
- Weapon of a hit: thrown object = its kind; otherwise the object slot 4-7
  held by the fighter (`$56` bit 6, `$03B7` = holder); otherwise fists.
  Kinds (room lists bank 13 `$B757`, gang weapon table bank 4 `$BF3E`, held
  weapons drawn per kind): `$08` rock, `$09` brass knuckles, `$0A` stick,
  `$0B` pipe, `$0C` chain, `$0D` tire, `$0E` box, `$0F` trash can.
- Damage: `$07`, latched at bank 5 `$8CF4` (`sec / sbc $07` -> `jsr dmg_latch`).
  bonus = min(damage, 24) / 4: strong += bonus, weak += bonus / 2, ticks += 2 * bonus.
- LAND, LAND_KO (+3 strong, at least 14 ticks), TAKE and OBJECT (+2 strong)
  use the weapon profile; BLOCK, BOSS and KNOCKDOWN keep the fixed table and
  the same priority order. Intensity is on the strong motor (DS3 weak is on/off).
- Envelopes: FLAT, DECAY (strong -1 per tick, floor 2), RATTLE (strong
  alternates with 2 every tick). Table: `WPN` lines in `snes/rumble.asm`.
- New RAM `$7EF808-$7EF80D`. Code: `$6B00` (481/512 bytes), `$6D24`
  (110/220), `$6F08` (237/248), banks 1-8.
