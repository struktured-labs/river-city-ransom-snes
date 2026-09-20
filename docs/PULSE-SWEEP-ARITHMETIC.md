# Pulse-1 sweep arithmetic correction

September 18, 2026. Experimental implementation, **not deployed**. Rival remains on
`071c89e9dde88bcc5622ef6379522149e72415b51b3418a8f281f5a66774733f`.

Review and native audio: <http://127.0.0.1:8766/pulse-sweep-review-1070/>.

## Actual bug and correction

The pinned legacy SPC image unconditionally subtracts one from the shifted pulse-1
sweep amount, then adds or subtracts that adjusted amount. This is wrong in both
directions. The correct period-increase amount is unmodified; period decrease
subtracts one extra on pulse 1. The pinned FCEUmm `FrameSoundStuff` implementation
and [NESdev's sweep reference](https://www.nesdev.org/wiki/APU_Sweep) agree.

For period 172 and shift 4:

| Operation | Legacy target | Correct target |
| --- | ---: | ---: |
| Increase period (lower pitch) | 181 | 182 |
| Decrease period (higher pitch) | 163 | 161 |

`tools/correct_pulse_sweep.py` checks both original instruction sequences before
changing them. It replaces the unconditional decrement with eight NOPs followed
by a branch over three padding bytes, and changes the decrease path's SETC to
CLRC. The extra borrow implements pulse 1's extra subtraction. The replacement
takes the same **20 SPC clocks** as the original block; an initial 18-clock
proposal was rejected by actual instruction execution before game integration.

The correction is default-off behind `--experimental-pulse-sweep` in
`tools/build_native.py`. It can be reproduced with the other flags and ordered
trace manifests recorded in the parent manifest. Rebuilding with it disabled
reproduces the current branded Rival ROM byte-for-byte.

Candidate: `build/pulse-sweep-branded-1059/native-cpu.sfc`, SHA-256
`275eeddd829bb9dc119f22429488639da54ad243cee83bccb8c4f71aa751feab`.
Only 17 ROM bytes change: 13 inside the embedded SPC image and four checksum
bytes. Game code, graphics, splash and controller mappings are unchanged.

## Executed arithmetic test

`tools/spc_sweep_probe.inc` adds an explicitly invoked diagnostic entry point to
a separate Snes9x build in `.deps/snes9x-sweep-1054/`. It loads supplied engine
bytes and executes the real SPC interpreter from `$09FC` to `$0A4C`. It does not
reimplement the SPC arithmetic in Python or change any production core.

`tools/check_pulse_sweep.py` executes every period 8–2047, shift 1–7, and both
directions: **28,560 cases**. Results:

- Legacy: 28,560 wrong arithmetic targets.
- Corrected: zero wrong targets; zero instruction-cycle differences.
- Three executed mutants are rejected: restored unconditional decrement,
  omitted extra borrow, and incorrect timing padding.

This checks target calculation before overflow/muting, not divider clocks or
complete APU behavior. Evidence: `build/pulse-sweep-executed-1055/report.json`.

## Game checks

Normal candidate capture 1060 completes the route in 9,403 frames. Its SPC
observer 1061 matches the entire frame/RAM/WAV timeline. All **8,950 packets**
match actual receiver stores; processing takes 187–1,261 SPC ticks.

Sparse main observer 1066 is independently neutral to the normal candidate.
Every sampled stable iteration still takes exactly two native NMI ticks:

| Room | Complete stable iterations | Tick count |
| --- | ---: | ---: |
| 0 | 601 | 2 |
| 1 | 1,745 | 2 |
| 2 | 476 | 2 |
| 3 | 1,003 | 2 |

All qualified start spacings are also two frames. The report retains 68
non-stable iterations and ten censored/outside-main observations. Renderer
capture 1067, cadence audit 1068, and hold audit 1069 retain all long stops and
find zero short 1/3/4-frame uniform-endpoint holds in either park direction.

The old run is 8,934 frames; this is **not** an equal-work speed comparison.
First differences: audio callback sample offset at frame 1022; game-RAM byte
`$01F9` (stack) at 1023; visible frame at 1162; native NMI count at 5935; delivered
scenario input at 7357. Later encounters diverge. No full-game/physical speed
or exact-background publication pass is inferred.

## Audio evidence and limitations

New `tools/capture_pulse_stem.py` isolates pulse 1 or 2 only in the host mixer,
without changing the game or its ordered APU writes. It restores the existing
isolation policy on exit and verifies all requested mixer options were consumed.

Pulse-1 clips use source frames 960–1150 from old game 1062, candidate 1063, and
NES ordered-write replay 1064. Both game stems retain their normal non-audio
timelines. All 192 packet byte sequences match, but ten publication frame labels
differ by one frame near the end of the window. These are retained, not aligned
away. Clips keep original rates and sample values, without gain fitting,
resampling or time stretching. Six original game checkpoint frames accompany them.

An exploratory pulse-2 comparison (captures 1052/1053) led to this source audit:
pitch sweeps differ even with the same input commands. The pulse-1 correction is
real but **does not eliminate the separate sweep-divider/timing discrepancy**.
No causal claim is made for the previously reported intermittent combat sputter.

Validation: **767 unit tests pass**, executed arithmetic cases and mutation checks
pass, and `git diff --check` passes. No physical restart, input, or audio settings
changes were made during this turn.

## Next work

Keep the full speed/scrolling/audio goal open. Trace the actual sweep divider and
reload timing against NES half-frame updates; do not tune pitch values to mask a
clock/phase error. Qualify the candidate's affected sounds on Rival before
promoting the flag or claiming a physical audio improvement. Existing combat gaps,
strict publication gate, and full-game qualification remain open.
