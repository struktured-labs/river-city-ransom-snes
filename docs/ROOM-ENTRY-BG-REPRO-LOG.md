# Issue #8 reproduction log (4305e, then 4305f)

All emulator runs headless: `tools/mesen/run.sh` = private `xvfb-run -a`, `WAYLAND_DISPLAY` unset.

## Tooling (checkpoint 1, 2026-10-14)
- `tools/mesen/password.lua`: types a 33-char NES password on pause > PASSWORD
  (grid layout mapped from screenshots; menu cursor = `$06D0`, pause flag = `$3F`),
  `setSkill()` via pause > LEVEL (Right cycles `$064C`).
- `tools/mesen/vis_check.lua`: every 4 settled frames compares **every** BG tilemap
  row (any `$1D00` state) to the converted NES shadow, and each BG CHR slot in VRAM
  to the pre-converted ROM bank picked from live MMC3 regs (`prepare_chr` mapping).
  Hit = difference lasting >= 180 frames. Positive control: 1 poked tilemap word and
  1 poked CHR byte are both reported (`/tmp/vc0`), baseline 0.
- `tools/mesen/room_bg_late.lua`: password -> Intermediate -> walk/fight (Y/B random)
  through areas, I->G->I via LEVEL every 2 areas, both checkers + row invariant on.
- Mesen2 RAM power-on is already `Random` by default; "strict" adds
  `EnableRandomPowerOnState` + `EnableStrictBoardMappings`. Strict runs were
  frame-for-frame identical to default ones (game initialises everything it reads).

## Matrix 1 on 4305e (60k frames/run, 3 passwords x {default, strict} x 2 seeds)
Passwords: P1 endgame `fnUlhbPcXZv c7173ZkSVpf WvdsalxgTZT`, P2 "final boss"
`XfMdZTHwiR3 jaj6jfRUDEt tilm2tWRo8b`, P3 "Ivan beaten" `t1izvpdOZnZ JxNkJp7Cpub XMPQgXErSMF`.
All three place the player at Cross Town High (passwords restore stats/bosses,
not location); walker reaches Cross Town <-> Sticksville (exit is up-right), not the park.
Result (all 12 runs complete): **0 row hits, 0 CHR hits, 0 persistent invariant
violations**; 18-52 area loads (incl. menu screens) and 6-19 I->G->I switches per run,
~14.5k settled checks per run (~175k total).

## Hardware (rivalmage)
2026-10-14 ~12:30 ET: CORENAME=SNES; OBS (recording since 10-13 23:32) shows a
different SNES game mid-dialogue. Not idle -> nothing launched or injected.
Existing tooling for later: `tools/mister_pad_sequence.py` (evdev via his USB pad,
refuses if pad not idle), `tools/obs_hardware_probe.py` (OBS screenshot).

## Accuracy emulator: bsnes (checkpoint 2)
- Built bsnes libretro core (`~/rcr-work/emu/bsnes`, upstream HEAD) with a small
  patch exposing WRAM and accurate-PPU VRAM via `retro_get_memory_data`.
- `tools/bsnes/host.py` + `tools/bsnes/run.sh`: headless ctypes libretro host
  (no DISPLAY/WAYLAND), runs the same Lua scripts through an `emu` shim (lupa/Lua 5.4).
  Options: accurate PPU (ppu_fast OFF), VRAM blocking ON (writes outside
  VBlank/forced blank rejected), entropy High (random power-on RAM/VRAM/regs), hotfixes OFF.
- Positive control `/tmp/vc0.lua` on bsnes: baseline 0 hits; poked tilemap
  word and CHR byte both detected. ~90 fps per instance.

## Hardware re-check (checkpoint 3, ~13:20 ET)
CORENAME still SNES, no pad input in 45 s, OBS shows the same non-RCR SNES game
frozen on the same dialogue as at 12:30 (left mid-session, unsaved progress).
Loading another cartridge would end that session, so still nothing launched.
Needs Carmelo's OK (or him returning MiSTer to the menu) before the hardware run.

## bsnes matrix on 4305e (checkpoint 4)
P1/P2/P3 x 2 seeds, 40k frames each, I->G->I every 2 areas, walking/fighting:
**0 row hits, 0 CHR hits, 0 persistent invariant violations** (14-19 area loads,
4-6 switches, ~9.8k settled checks per run).
bsnes menu-load stress on 4305e (`room_bg_loads.lua`, pause submenus + LEVEL skill
changes + street play, 3 seeds): 901 loads, 866 post-load full-row checks,
**0 stale rows, 0 persistent invariant violations**; avg 19.2-19.7 blank frames/load.

## 4305f regression on bsnes (checkpoint 5): running /tmp/bx-f
