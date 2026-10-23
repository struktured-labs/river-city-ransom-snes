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

## 4305f regression on bsnes (checkpoint 5, done ~14:05 ET)
Same `room_bg_late.lua` setup as checkpoint 4, cut to 3 runs (P1-s1, P2-s2, P3-s1)
because blackmage load was ~36; the other 3 were stopped early.
**0 row hits, 0 CHR hits, 0 persistent invariant violations**: 17/17/23 area
loads, 5/5/8 I->G->I switches, ~9.7-9.8k settled checks per run.
Blank frames per street-area load (mean of the logged loads after boot):
4305e 23.2/23.2/24.9, 4305f 28.5/27.8/29.8 (about +5 frames, same as on Mesen).
Note: 4305f logs "repaired row N after 5783 frames". These are rows that already
differed at frame 0 (random power-on VRAM, before the checker was gated off)
and were first re-checked once checking resumed. Not a violation.
Conclusion: 4305f is clean wherever 4305e is clean. 4305e itself has not
reproduced #8 on Mesen2 or bsnes, so this is a regression check only, not proof of a fix.

## Area coverage (checkpoint 6, started ~14:30 ET)
- NES area tracker is `$0042` (FCEUX RAM map: 00 Cross Town ... 04 Sherman Park ...
  0x1B Burb Village, 0x1C+ River City High). Teleport = hold `$0042` at the target
  only while the game's own area load runs (`$1CA0 != 0`); the game's load routine then
  builds the target area normally (verified: Sherman Park restroom backdrop with goons).
  Writing `$0042` before the transition (what the RAM map warns about) gives broken BG, so not used.
- `tools/mesen/room_bg_tour.lua`: legs = teleport-load into target, fight 300-900
  frames, I->G->I mid-fight (60% of legs), fight, then a NATURAL exit + fight in the
  neighbour. Default targets: 04 04 06 07 09 0a 0d 0f 10 11 13 14 18 1a 1b 04.
- Smoke (Mesen, 3 legs): reached 04 park, 06, natural loads into 03/05/07; 0 hits.
- 14:34 ET: Carmelo approved. Closed the other SNES game; loaded 4305e MGL. P1 SNAC set Yes->No in OSD (Input Options) so USB pad injection reaches the game; MUST restore to Yes at end.
- Hardware driver: `tools/mister_rcr_hw.py` (pad chunks via run_mister_keys --pad, OBS
  screenshots, password typing) and `tools/mister_rcr_hw_loop.py` (CT <-> Sticksville
  transitions with goon fights, I->G->I via LEVEL every 2 transitions, pause-repair
  delta per arrival: paused shot P1, unpause/re-pause, P2, backdrop diff).
  Endgame password typed and accepted on hardware. Walking out of Sticksville to the
  park was not achieved by blind input (exit ramp + goons; Alex died twice -> CT respawn).
- HW run e3 (4305e, ~15:10 ET): 16 CT<->Sticksville transitions with goons, 8 I->G->I
  switches (LEVEL screens verified in shots), Alex near death several times.
  Pause-repair delta: backdrop diff 0.0 on all 16 (11 pairs proven valid by sprite
  motion between P1 and P2; 5 pairs identical = re-pause missed). All 16 arrival
  backdrops visually correct. **No repro on hardware so far.**
- bsnes tour e2 one VC-HIT: row 72 in Waterfront Mall (06) was *pending* (state 1/3,
  being rewritten while scrolling) for 180 frames, not a clean stale row; the screenshot
  is correct. Treated as checker noise for pending rows, not #8.

## Checkpoint 7 (~15:25 ET)
- HW run e4 (4305e): 16 more CT<->Sticksville transitions before the walker got stuck
  in Cross Town and its blind inputs ended on the password screen (nothing submitted).
  Stopped at 15:18.
- **SNAC restored** to Yes in OSD > Input Options (screenshot `hw/snac1.png`), OSD closed.
  `SNES.CFG` sha256 `066fa49a...d933` is unchanged from before the session. 4305e MGL
  reloaded to a clean boot; CORENAME=SNES (RCR 4305e).
- Extra park-route HW run **not done**: in Mesen, 12k frames of 6 movement patterns at
  the end of Sticksville (01) never reached Grotto Mall (02), so there is no known
  input route to the park. Passwords always restart at Cross Town. A blind HW attempt
  would need SNAC off again for little expected gain.
- bsnes tour e2 (Ivan pw, 32 legs) done: 147 loads, 15 I->G->I, 58.6k settled checks,
  visited 00 03 04x6 05 06 07 09 0a 0c 0d 0e 0f 10 11 12 13 14 18 19 1a 1b.
  0 CHR hits, 0 persistent invariant violations; 1 pending-row hit (see above, not #8).
- bsnes tour e1 (endgame pw, 32 legs) done: 171 loads, 24 I->G->I, 73.4k checks, **0 hits**. Mesen tours mtour-e1 (default targets) and mtour-e2 (late targets 10-1b, 0b, 08) running.
- Mesen tour mtour-e1 (Ivan pw, default targets, 32 legs) done: 177 loads, 16 I->G->I,
  51.8k checks, visited 00 03 04x6 05 06 07 09 0a 0c 0d 0e 0f 10 11 12 13 14 15 19 1a 1b: **0 hits**.
- Mesen tour mtour-e2 (endgame pw, late targets) stopped at leg 20 (walker stuck after
  area 17): 111 loads, 13 I->G->I, 52.5k checks, visited 0e-17 incl. 11/12 x16: **0 hits**.

## Summary at ~16:15 ET
Issue #8 has **not reproduced on 4305e** in any of these:
- Mesen2: 12 late-password runs, 1 park/late tour, 900+ menu loads.
- bsnes accuracy core: 6 late-password runs, 2 tours of all areas, 901 menu loads.
- Hardware: about 34 transitions with I->G->I switches and goon fights; every arrival backdrop was correct.
Since 4305e never failed, there was nothing to rerun on 4305f under identical inputs.
4305f's own regressions (bsnes checkpoint 5, Mesen 2.5k loads) are clean.
Not covered: the park on hardware (no input route found) and a
real long play session (several hours, with save/continue).

## Checkpoint 8: long sessions (started 2026-10-14 ~23:20 ET)
- `tools/mesen/room_bg_long.lua`: one power-on, no resets, Intermediate start, random
  segments (teleport legs, natural exits, goon fights, forced deaths + respawns, pause menus
  incl. PASSWORD view, quick I->G->I, long Gamer stretches, Up-into-door + A/B mashing).
  vis_check with `VC_SKIP_PENDING=1` (rows with `$1D00` != 0 skipped), per-frame row invariant,
  10-emu-minute CK lines with row-state histogram + `$1C00-$1CBF` bookkeeping hex.
  Inputs RLE-logged (`inputs.txt`); bsnes host gained `emu.saveStateFile/loadStateFile`
  (retro_serialize), savestate every 18000 frames (last 3 kept), WRAM+shadow dump + state on hit.
- Smoke (bsnes, endgame pw, 32k frames): 15 loads, 0 hits; states + inputs written.
- Runs: bsnes seed 11 `/tmp/long-b11`, Mesen2 seed 21 `/tmp/long-m21`, 864k frames (4 emu h) each.
- Not covered: 2P (no second-pad driving yet), real shop purchases (door attempts only).
- 2026-10-14 23:59 ET: runs survived the interruption (b11 0.55 emu h, m21 2.34 emu h, 0 hits),
  reniced to 15. Detached finishers (`tools/longsession_finish.sh`) copy each run into
  `build/longsession/<id>/` and append a line here on exit; m21's finisher then starts Mesen
  seed 22 (`tools/longsession_run.sh m22 mesen 22`). Status: `tools/longsession_status.sh`.
- long-session m21 ended 2026-10-15 00:20 EDT: HIT lines 0; last: `[f865796] SUMMARY loads 395 segs 314 VC 214182 row 0 chr 0 invP 0 hits 0`
- long-session m22 ended 2026-10-15 01:12 EDT: HIT lines 0; last: `[f871176] SUMMARY loads 623 segs 354 VC 214355 row 0 chr 0 invP 0 hits 0`
- long-session b11 ended 2026-10-15 02:22 EDT: HIT lines 0; last: `[f868252] SUMMARY loads 923 segs 399 VC 211939 row 0 chr 0 invP 0 hits 0`
- long-session shopsmoke ended 2026-10-21 15:36 EDT: HIT lines 0; last: `[f048605] SUMMARY loads 26 segs 16 VC 11658 row 0 chr 0 invP 0 hits 0`
- long-session m24 ended 2026-10-21 16:26 EDT: HIT lines 0; last: `[f866220] SUMMARY loads 809 segs 343 VC 212400 row 0 chr 0 invP 0 hits 0`
- long-session m23 ended 2026-10-21 17:43 EDT: HIT lines 0; last: `[f2161930] SUMMARY loads 1755 segs 917 VC 531586 row 0 chr 0 invP 0 hits 0`
- long-session s1 ended 2026-10-21 17:45 EDT: HIT lines 0; last: `[f1950721] SUMMARY loads 1496 segs 745 VC 479197 row 0 chr 0 invP 0 hits 0`
- long-session b13 ended 2026-10-21 18:33 EDT: HIT lines 0; last: `[f868052] SUMMARY loads 905 segs 410 VC 211810 row 0 chr 0 invP 0 hits 0`

## 2026-10-21 opt-in segment modes (grinding / death-redo / weapons / combos)
RAM used (from docs/SHOP-QOL-MECHANICS.md, tools/capture_shop_qol_mechanics.py, tools/build_gamer_item_caps.py, docs/RUMBLE.md):
stat i of player p at `$049F + 4*i + p` (punch, kick, weapon, throw, agility, defense, strength, will, stamina `$04BF`, max power `$04C3`);
caps 63 for stats 0-7 (127 via Gamer item consume), max power 127; password stat slots `$058E-$0595`; money `$04C7-$04C9` BCD.
RCR has no XP. Objects: slot kind `$00CB+s` (`$08` rock .. `$0F` trash can), held = `$0056+s` bit 6, holder `$03B7+s`, x = `$008C+s`/`$0083+s`.
- `room_bg_long.lua` (Mesen + bsnes): `GRIND=1 REDO=1 WEAP=1 COMBO=1 [WPOKE=1] [NEWP=0.35]`; per-segment `seg` log lines and a `new ...` CK field.
  Smoke (seed 7, 49k frames): pickups work; held weapons are always dropped by room loads (kept 0/2), so WEAP throws in place 40% of the time.
- `mister_rcr_blue_loop.py`: same env names, input-only (no RAM on hardware); `death_redo` events keep heading + door mash after an empty HP bar.
- `tools/mister_blue_waiter_bl3.sh`: starts bl3 (seed 33, all modes) after bl2 exits, only if no STOP/HANDOVER file, no foreign SSH peer and RCR_4305e.mgl still loaded.
- Launched 20:43 EDT on 4305e: m25 (mesen, all, WPOKE), m26 (mesen, all + SHOP), b14 (bsnes, all, WPOKE), b15 (bsnes, GRIND+COMBO, NEWP 0.5).
- long-session m25 ended 2026-10-21 21:45 EDT: HIT lines 0; last: `[f869242] SUMMARY loads 893 segs 244 VC 212725 row 0 chr 0 invP 0 hits 0`
- long-session m26 ended 2026-10-21 21:45 EDT: HIT lines 0; last: `[f879834] SUMMARY loads 702 segs 221 VC 216248 row 0 chr 0 invP 0 hits 0`
- long-session s2 ended 2026-10-21 22:55 EDT: HIT lines 0; last: `[f1954492] SUMMARY loads 2041 segs 962 VC 476481 row 0 chr 0 invP 0 hits 0`
- long-session b12 ended 2026-10-21 23:31 EDT: HIT lines 0; last: `[f2162210] SUMMARY loads 1363 segs 800 VC 533251 row 0 chr 0 invP 0 hits 0`
- long-session b15 ended 2026-10-22 00:01 EDT: HIT lines 0; last: `[f867622] SUMMARY loads 1881 segs 267 VC 207209 row 0 chr 0 invP 0 hits 0`
- long-session b14 ended 2026-10-22 00:03 EDT: HIT lines 0; last: `[f871241] SUMMARY loads 940 segs 215 VC 212848 row 0 chr 0 invP 0 hits 0`

## 2026-10-23
- blue loop: death_skip also on the "ALEX has lost all" text box (IoU vs tools/mister/lost_all_mask.png >= 0.6) or any dialogue text without a pause menu; fixes false HITs bl2_t00157 / bl3_t00040 (pit deaths, HP bar not empty). bl3 stopped at k 2500 / 90 transitions (STOP-bl3), bl4 (seed 34, all modes) started 11:2x EDT.
- GRIND now retries LEVEL until \$064C == 3 and logs grind skill/max; smoke seed 9: 5/5 grinds in Gamer, stats 121-127.
- Launched m27 m28(SHOP) b16 b17(SHOP), all modes, on 4305e.
