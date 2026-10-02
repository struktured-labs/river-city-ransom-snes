# Build 4302: check suite and issue verification (2026-10-02)

ROM `build/gamer-stam-cap-4302/native-cpu.sfc`, SHA-256
`3d8b611292ff615290195ea9d3f79669cafba051cdffd8b0cafab2557cb85f16`, CRC32 `2351783E`.

## Check suite

| Check | Result |
| --- | --- |
| snes9x freeze batch (66 runs) | 0 hangs |
| Mesen2 freeze batch (60 runs) | 0 hangs, 0 bad-DB interrupts |
| snes9x outline checks | 9/9 |
| Unit tests | 1644 run, 1 failure (pre-existing `test_chromatic_wub`) |
| Stamina sweeps | Gamer monotonic, empty only at 0, full from 241; Novice equals NES for 0–255 |
| Mesen2 timing | default max vblank line 257, Gamer 258; 0 batches end in active display |
| Mesen2 rumble R0–R6 | pass after the R1 whitelist fix below (4295 also passes) |
| snes9x rumble S0, S2–S4 | pass |
| snes9x rumble S1 (BOSS pulse seen) | **fails** on the base trajectory, offsets 0 and 37; passes at 101 |
| Mesen2 outline checks | **fail** 4, 5, 6, 9 (see below) |
| Mesen2 bridge (`bridge.lua`) | NMI/return/skip pass; "screen keeps changing" fails (stuck=11), same on 4301 |

Why the failures are not 4302 regressions:

- **R1** flagged `$7EF807` writes from `c1:6e99`. That is `rumble_latch` in
  `snes/autojoy_compat.asm` (4299), which records the sent level in `R_SENT` by design.
  `tools/mesen/rumble.lua` now allows that one routine. 4302 and 4295 then pass R0–R6.
- **S1** needs a BOSS pulse on a fixed trajectory. Mesen R2 (69 hooks, 0 classification
  mismatches) and R6 (forced boss class, 5 boss hits) pass. Across 8 input offsets,
  a BOSS pulse showed up on 4295 7/8, 4299 6/8, 4300 7/8 and 4302 4/8, with a class-9 boss
  present in every run. A KNOCKDOWN pulse (7) outranks BOSS (6) by design. This is a
  coverage limit, not a defect, but the check does fail as written.
- **Mesen2 check 4** failed on one frame (f5527) with 4 sprites. `OAMTRACE` shows SNES OAM
  holding the NES sprites from 4 frames earlier, while the harness allows 3. This happens
  while the screen is already black (screenshots `mm-005525..9`), so nothing is visible.
  The same mismatch class shows up in the same harness on 4295 (f13865), 4299 and 4300
  (f33057, f42880). 4301 and 4302 runs are frame-identical.
- **Checks 5/6** need goons on screen. On this trajectory `goonSpr=0`. They fail the same
  way on 4299 and 4300.
- **Check 9** fails in the full run on 4295 too. On 4302 the focused carry run also has
  carry-phase OAM-lag mismatches. The carried-goon metrics are clean:
  carriedSpr=408, unred=0, linkBad=0, afterUnred=0.

## Issues

- **#24 / #27:** Forced boss spawns (types 9/11/13/16/19, `tools/mesen/bossforce.lua`
  and `tools/bossforce_nes.lua` in FCEUX) give these stats on 4302:
  - Novice and Advanced rows equal the NES byte for byte (Advanced = Novice + 16).
  - Intermediate is Novice + 8, exactly midway.
  - Gamer is Novice + 32.
  - X is kept on every spawn. `xclobber.lua` passes on skills 1/4/2/3.

  On 4299 Intermediate, the boss rows came out as 0 or 1 stamina, and the stats were
  written into Alex's row and `$04C3`. That explains the one-shot boss.
- **#25:** A write watch on `$04BF`/`$04C3` (Intermediate) shows extra writers on 4299:
  the spawn loop at `c5:b886` and `c5:b88f`. On 4302 only the game's normal writers
  remain (damage `c5:8cfe`, init `c7:dfbc`, `c7:f6f9`, `c7:f6ff`).
- **#28 / #29:** Spawns no longer touch Alex's stats, and player caps outside Gamer
  stay 63/127. The garbled password and the soft lock were not reproduced directly.
- **#30:** `bridge.lua` passes its NMI/return/skip checks on 4302, matching 4301.
- **#26:** Not reproduced. Runs covered:
  - `rightedge.lua` (rooms 0–3, Intermediate running, Gamer running and walking);
  - Gamer accept and carry runs with a right-edge red-transient detector (about
    70,000 frames).

  No transient red was found. The only right-edge sprite anomaly (stale OAM) happens
  during a blanked frame.
