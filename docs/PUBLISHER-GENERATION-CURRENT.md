# Compact sprite-generation marking and retained-NMI phase experiment

Combined candidate `build/publish-combined-565/native-cpu.sfc`, SHA256
`f26179d74a94978f97cb224f509bfae0ce307c8ce1097b63dd9f8fd2bbac4397`.
Not promoted or deployed. Retained comparison remains539; fresh disabled
control565 reproduces its cartridge byte-for-byte.499 Python tests pass.
Original-speed, full scrolling latency and audible/physical sound gates remain
open. No Rival reset.

## Actual implementation

Enabling the existing generation-gated final DMA option initially failed to
link: the CODE segment exceeded its bank by472 bytes (attempt562). The
unrolled delta sprite converter repeated `LDA #1 / STA $1CEE` in each changed
word branch, potentially128 stores per producer call.

`sprite_delta.inc` now saves Y, initializes it to zero, increments it for each
changed word, and sets the dirty generation once at the end if needed. There
are at most128 increments; the A8 nonzero test cannot lose a full-wrap change.
Y is restored. A no-op pass does not clear an already pending generation.
All of this remains inside the original interrupt-masked producer.

The initial DP-counter version still overflowed (563), and compact Y counting
alone still overlapped the header (564). In the delta+generation-gated
combination, `native_prepare.asm` now also omits the unreachable legacy sprite
converter after its unconditional jump to `prepare_tail`. Shared conversion
tables remain present. The disabled comparison layout stays identical. The
production combination now links; no ROM memory-map expansion was made.

New optional `experimental_deferred_resume_line` controls only the port's
retained-NMI phase threshold after bounded video publication. Default remains
250; opt-in tests use240. Only integer240..250 and the NMI-only deferred
scheduler are allowed. The nine-bit beam guard, fresh-event handling, early
sound service, anti-tearing rule and original game waits remain intact.

## Executed tests

- `sprite-dirty-oracle-567`:27 successive complete544-byte OAM/snapshot
  comparisons, both pattern halves, initial/all128-word changes, isolated
  source edits, unchanged input, reinitialization and pending-generation
  preservation. Y/DB/DP/width checked. Five executed mutants rejected:
  missing mark, missing count initialization, lost pending flag, lost Y and
  ignored attribute/X change counting. The complete production publisher
  pixel fixture also passes, including palette-only channel initialization.
- `deferred-phase-oracle-570`:36 real-beam cases, thresholds240/250, lines
  230..260 and two instruction offsets. Exact extracted production guard
  checks finish interval, X/Y/stack and unrelated publication state. Four
  actual mutants rejected: early cutoff, forced/ignored high bit, wrong
  scratch address. This is not a whole-interrupt worst-case-time proof.
- Existing structural test was updated to check both the conditional
  threshold and default250 branch; the disabled-ROM identity check is stronger
  evidence that default machine behavior did not change.

## Separate experiments, unchanged speed gates

All captures use the same fixed input scenario; replay totals are not speed
ratios. Entry reports568 retain all original NES-relative fade/image gates.

| Build | First/second/third whole loads | First visible offsets |
| --- | --- | --- |
| NES |20 /31 /30|7 /7 /7|
| Retained539 / control565 |21 /28 /29|7 /6 /7|
| Dirty final DMA only565 |22 /29 /29|8 /7 /7|
| Earlier resume only565 |21 /28 /29|7 /6 /7|
| Combined565 |22 /29 /29|8 /7 /7|

All remain failures. Earlier-resume-only PCM is identical to the retained
fixed run, but timelines are not identical; this is not asserted state parity.

`audit_deferred_phase.py` groups repeated poll entries into complete waits
and rejects missing/truncated intervals. Reports572 are fully observer-neutral:
parent539 has six248-clock guard intervals in7548..7560; dirty-only has ten
248-clock intervals and one4,432-clock wait (line247→250) in7540..7565;
combined has ten248-clock intervals in that latter window. These are different
execution histories, not rematched calls. The phase guard is usually already
past its threshold: simply lowering it does not solve the sampled deadline.

## Combined build qualification and limits

- Full adaptive renderer:8,803 frames, entire timeline/PCM neutral. Split
  audit573 checks1,198,240 lines across7,489 eligible frames: zero splits.
  It records737 frame-end committed-camera differences, which alone are not
  missed deadlines. Original broken split is still detected.
- Status audit573: both Present Status entries pixel-exact.
- Full fixed audio run571:9,406 frames neutral to normal566. Provenance573
  verifies all212,336 actual SPC receive stores across9,232 paired packets,
  not merely CPU writes or four header fields. Zero mismatches; key-on and
  ready checks pass, processing161–1169 SPC ticks. No acoustic/physical pass.
- Park audit574: no stable interval above1.5frames. Neutral574: no late NMI
  interval in7600..8420. These are scoped observations, not full-game endurance.
- Full background capture575 and audit576 are retained separately; their
  667 selected backgrounds match exactly, but coverage259/42/133/233 fails
  the unchanged64-sample room minimum. Publication and settling gates also
  fail. These gates are not replaced by the split-only check.

Next: continue measured producer/decode/main-thread optimization. Keep both
new policies experimental until actual loading/deadline gains outweigh their
scheduling regressions. Review: `http://127.0.0.1:8766/publisher-review-577/`.
