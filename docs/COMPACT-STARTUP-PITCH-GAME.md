# Restart-pitch staging in the full game

Follow-up: [menu/DMA qualification, video-stage diagnosis and lower-cost3219](STARTUP-STAGING-VIDEO-TIMING.md).
The results below describe the preceding3190 milestone, not the later variant.

[Qualification collage and native combat audio](http://127.0.0.1:8766/balanced-startup-pitch-qualification-3200/).
[Restart timing, parent/trial audio, and changed frames](http://127.0.0.1:8766/balanced-startup-pitch-review-3198/).

Offline candidate3190 integrates the restart-pitch experiment into the full
game without increasing the 12,415-byte SPC upload or changing game CPU code,
graphics, controllers, or the loader. It is not promoted or deployed. Neither
MiSTer nor OBS was operated; Rivalmage remains off-limits and Bluemage's physical
capture connection remains unconfirmed.

- ROM: `e1d5936b580f9faa6b766658e99b2e8537be843366dc292e0dd2c3850b47a2ea`
- SPC: `d320d7a933a6b1543cd4981c13a2fe2a9546229246e2a7de5de5a1f4da5d07c1`
- Candidate: `build/balanced-startup-pitch-game-3190/native-cpu.sfc`
- Parent: retained ordinary-early-audio3065.

## Implementation

`build_compact_startup_pitch.py` fits guarded staging wrappers, pitch storage,
ordinary publishers and restart flush into verified existing SPC padding.
The live receiver helper at $2FA0–$2FA9 is explicitly preserved. Only the engine
and cartridge checksum regions may change. Pending-restart pitch writes occur
after KON during actual DSP startup silence; source and volume stay before KON.
Ordinary pitch updates retain the existing five-clock low/high write gap.

`build_balanced_startup_game.py` removes six clocks from the compact variant's
zero-pending flush. This skips clearing staging validity only when no restart
is pending: staging sets the corresponding pending bit and every completed
restart clears validity. Restart paths still clear both validity and pending.
The adjustment reduces overhead but does **not** eliminate cross-ROM picture
differences. Compact3182 remains retained as the earlier experimental version.

## Executed evidence

State3192 executes 201,060 cases with all final DSP registers and application
state matching the original engine. Only the two DSP MMIO shadows $F2/$F3 are
exempt; 42,479 cases differ there. An executed stale-validity mutation fails
25 of 4,452 selected cases. All 16 continuous timer/receiver checks pass.

| Pending restart mask | Additional SPC clocks observed |
| --- | --- |
| 0 | 0, 32, 64 |
| 1 or 2 | 124, 156, 182, 214 |
| 3 | 124, 182, 240 |

Game normal3191 and observed3193 match exactly with the same emulator core,
including native audio, inputs, RAM, timeline and images over 9,248 frames.
Audit3198 verifies:

- All 8,802 complete CPU packet records match parent3065, including payloads,
  source frames, native NMI identities and write counts.
- All 1,607 restarts publish pitch inside measured startup silence and start
  at the intended pitch: no wrong-first-pitch or stale nonzero onset. Actual
  game restarts cover all 64 KON-write clock phases.
- The previously observed packet6,222 pulse2 case writes pitch at SPC ticks
  113,228,581 and 113,228,593, after silence begins at 113,228,514 and before
  the first oscillator low-pitch read at 113,228,673.
- All 3,750 selected gameplay intervals remain two frames: rooms0/1/2/3 have
  601/1,745/478/926 intervals. The busy flag is not filtered from selection;
  no selected interval in this route is busy. This is scoped cadence coverage,
  not equal-work proof against the original NES.

Renderer3196 uses a separate same-core normal/observer pair3194/3195:
7,640 eligible frames, zero coverage failures, zero scanline splits and zero
stale camera frames. This does not substitute for tile, menu or DMA checks.

Combat3197 runs both running-jumps and sustained-attacks policies for 4,929
frames each, with fresh observer-off/on pairs. Both players' delivered inputs
and actual movement are checked. Each policy passes all 1,753 selected
two-frame intervals, including the busy-inclusive denominator. Full exclusions
and outliers remain in bound evidence. Qualification3200 combines these gates.

All 1,300 unit tests pass (log `/tmp/rcr-tests-3199.log`); `git diff --check`
passes. Source bindings and generated artifacts were revalidated. The web
collage was rendered and inspected. Its audio excerpts decode exactly to the
stated native source sample ranges, with no gain, resampling or phase fitting.
This is automated signal verification, not a claim to have heard an improvement.

## Retained differences and next gates

Compared with parent3065, candidate3190 has 365 different images, 8,462 frames
with nonaudio timeline differences and 830 audio callback-boundary differences.
Every differing field is retained in3198; its collage shows the first four
changed frames. The earlier compact variant had 362 changed images and 869
callback differences. Balancing the no-restart flush therefore did not close
cross-ROM equivalence. Passing same-core observer neutrality is a separate
claim and does not waive these differences.

Before promotion, rerun all four menu regressions and DMA qualification on this
exact ROM and investigate remaining cross-ROM differences. Broader original-NES
waveform/speed coverage and physical Bluemage audio/video remain open. The
earlier held-tone prototype still failed its low-pitch/narrow-duty reference
bound; the current work does not establish resolution of that failure, ordinary
update artifacts, noise fidelity, or the user's physical popping complaint.

No splash sound or controller-mode changes were made in this iteration.
