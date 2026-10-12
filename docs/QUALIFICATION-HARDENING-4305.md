# Qualification hardening, 2026-10-03

Release status: **hold 4304**, candidate 4305 is not yet a qualified release.
No MiSTer restart or configuration change was made in this investigation.

## Real black-screen fault behind the shifted-input successes

The unshifted snes9x rumble replay on 4304 becomes persistently black, and the
CPU sits at `$C2:31DD` (the invalid-bank guard), with A low byte `$41` instead
of a valid bank number. This is not merely failure to reach a pause scenario.

An instruction trace shows an NMI landing inside `enable_poll` at `$C2:6E08`
after its PLA, with the helper's PHP and JSR return still on the stack. RCR's
FC60 coroutine return consumes exactly the original interrupt frame and the
saved task/A. Those three extra stack bytes corrupt its continuation. The
original saved bank number remains on the stack, but the subsequent PLA reads
the wrong position. The guard correctly stops execution; it must not be removed.

4305 replaces only the FC60 enable-tail call with a stack-neutral jump to
`ORA #1 / STA $4200 / JMP $FC73`, replicated in eight banks. At this exact point
A is `$F8|$80`, so setting autojoy leaves the wait branch nonzero; the original
caller A remains in FC60's original stack frame. Normal automatic polling and
the separate rumble transaction remain intact. The SPC engine is unchanged.

Builder: `tools/build_autojoy_coroutine_fix.py` (exact-parent SHA guarded).
Candidate SHA: `4d22634627604c5dddc7bb3fcda479793f736b02128502116889ddd43d542a81`.
Parent SHA: `369d0066273992a6f2e10bc3d1d32239ceb4e89a87f276a0f5b048404adfe9f0`.

## Test corrections

- Pause is `$3F & $20`, not `$3F != 0`: `$40` and `$80` also describe menu
  transitions/display state. Poll the actual pause bit after a bounded press;
  log every attempt and fail if a requested transition never happens.
- Settings selection is bounded; a stuck selection cannot loop forever.
- `watch_rumble_liveness.py` retains every requested input, CPU registers,
  WRAM/video hashes, and native-rate PCM. It aborts as failure after 300
  consecutive black frames instead of continuing to label it missing coverage.
- The ident patcher now rejects an already-current splash curve. This fixes the
  previously known failing `test_chromatic_wub` without changing the ROM's sound.
- Outline tests no longer call sparse/dim content blank. Their eight-frame
  attribute matching is explicitly labeled as color-history matching, **not**
  publication latency. It cannot certify the original-speed requirement.
- A separate full-live-OAM generation trace and next-frame gate retain late and
  undisplayed generations. Delayed/dropped/blank-only negative fixtures fail.
  This start-frame snapshot probe is not yet a complete scanline-renderer audit.

## Fresh results

- Unit suite: 1,667 tests, OK with eight skipped (not full dependency coverage).
- Final parent/candidate liveness runs retain native 32,040 Hz stereo WAVs and
  bind the exact ROM, core, harness and WAV hashes in their `report.json` files.
  Captured PCM is not a claim of listening approval or pop-free audio.
- 4304: persistent-black failure at frame 7280 (300 consecutive black frames).
- 4305: 11,773-frame unshifted replay passes rumble S0–S4, three pause/resume
  cycles, and boss coverage (5 BOSS events); longest black span 25 frames.
- 4302 control: same revised replay passes, 10,158 frames. Gameplay trajectories
  differ across cartridges; do not interpret them as cycle-identical comparisons.
- 4305 Mesen: rumble R0–R6 pass; Intermediate and Gamer final video batches
  finish by scanline 257, never in active display in those routes. Gamer has
  3,226 measured batches over its street route.
- Publication probe, 1,800 frames each: 4304 has 74 late/undisplayed generations
  out of 860 known; 4302 has 67 out of 781. This is a failed strict gate on both,
  not evidence the audio-engine change caused all sprite latency. Exact raw
  events and per-generation details remain in the local reports.

Local evidence directories are `build/qualification-*`. Failed earlier probes
remain intact. Do not reuse old reports after their bound tools change without
checking those hashes. The ROM build artifacts themselves remain immutable.

Web audit: `http://localhost:8766/qualification-review-4305/index.html`.
Stack corruption tracked at https://github.com/struktured-labs/river-city-ransom-snes/issues/32.

## Still open

- Exact-build SNAC buttons **and motors**, P2, and original SNES/EverDrive tests.
- Strict publication latency and the intermittent right-edge flicker (#5/#26).
  A detector finding nothing in a route is not proof that the report is fixed.
- Password UI round trips and extended-stat policy (#28): no encoder/decoder
  or lossy stat-clamping change is implied by this repair. Extended passwords
  are still not implemented; do not claim Gamer stat persistence.
- Re-run broader game/audio checks before updating release hashes or packaging.
