# Owned graphics work yields to queued real interrupts

Offline candidate 2990 removes the remaining three-frame start interval in the
fresh running-jump campaign. It is **not qualified for deployment**: the earlier
2239 saved-state picture gate still fails, and sound is not certified pop-free.
Neither Rivalmage (occupied) nor Bluemage was accessed during this work.

Candidate: `build/owned-queue-priority-trial-2990/native-cpu.sfc`

SHA-256: `24ed12f26c4f99d9a4d0ea139b794e41671ae3d16d874fc9cedb2ba183d3795e`

[Collages, exact native audio and bound evidence](http://127.0.0.1:8766/owned-queue-priority-review-3003/)

## Change

The previous queue-priority check ran only after the producer guard recognized
the retained-camera return frame. Hardware-entry preflight uses a different
return frame, so owned graphics preparation could run ahead of a queued event.

`build_owned_queue_priority.py` appends a helper to the existing 512-byte
retained-entry allocation and hooks the initial ownership load in all eight
guard mirrors. When `$1B80` owns preparation and `$1B87` records a queued real
interrupt, preparation returns deferred regardless of return-frame identity.
Nothing is cleared or consumed. With no queued event, original camera/deadline
admission remains intact. The existing hardware-entry and active-wait bytes and
entry addresses are verified unchanged. No graphics assets or SPC code change.

## Evidence

- Oracle 2991: 192 executed cases cover both preparation entries, ordinary and
  retained-camera frames, six beam positions, zero/nonzero ownership, queue
  counts 0/1/255, all eight mirrors and low stack wrap. X/Y, DP, DB, SP, saved
  interrupt frame and queue counters are checked. Two executed predecessor
  controls fail the new ordinary-frame admission requirement. Preparation
  endpoints are dispatch spies, so this is not graphics correctness proof.
- Fresh combat 2992: all 4,929 frames complete; normal/observed actual two-pad
  inputs and outputs agree. Strict phase cadence passes, including pause/resume.
  Busy-inclusive analysis has 1,753 two-frame intervals, no irregular intervals.
  This is one deterministic scenario, not whole-game or matched-NES parity.
- Instruction runs 2996/3000: complete output and PCM agree with the separate
  sparse-observer combat core. The new helper executes in the traced window.
- Exact state 2993 from parent 2944 at 2248: full initial WRAM/registers and
  actual controller inputs are preserved; the complete patch rebuilds byte for
  byte. Completion advances at 2250 instead of 2251; native counts and pictures
  match through 2252. Later differences remain in evidence.
- Restore-local trace 2997/2998: 90-frame observer neutrality, seven original
  bodies and sound packets with IDs 1860–1866 once in order, no unserved hardware
  flag expiry. Sender spacing still varies: 367824, 342354, 435044, 266138,
  443910, 270588 master clocks. This does not establish smooth DSP/audio output.
- Traversal 2995/renderer 2999/audit 3002: 9,248 frames, observer neutral, zero
  coverage, split or stale-camera failures. East park holds: 205×2 and 7×14;
  west: 154×2 and 7×14. No short irregular holds; encounter stops remain counted.
- Earlier state 2994: recovered event/completion counters remain correct, but
  fixed-picture equality fails at 2238/2239. Do not waive this gate merely
  because combat is faster. Full fusion/queue/retained/priority composition is
  rebuilt from the earlier parent without guest RAM fixups.
- 1,237 unit tests pass (`/tmp/rcr-tests-3001.log`); `git diff --check` passes.

Review 3003 binds the executed fixtures, separate observer receipts, actual
frame images and four byte-identical unnormalized 90-frame WAVs. New menu,
full-route DSP and physical qualification are still outstanding. Next work is
to explain/fix the earlier sprite-publication mismatch without regressing the
new combat timing, then qualify audio and menus before a Bluemage test.
