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
