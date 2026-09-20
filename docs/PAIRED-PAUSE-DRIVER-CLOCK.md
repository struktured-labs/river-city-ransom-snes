# Original NES pause driver: measured scheduling difference

[Paired native clips and exact event audit](http://127.0.0.1:8766/paired-pause-clock-review-3656/).
No ROM, default build, MiSTer, OBS or deployed configuration changed in this
investigation. Candidate3631 remains the latest isolated queue fix. The full
speed/scrolling/audio goal is active, with no physical/pop-free completion claim.

Fresh original NES control3652 and observed3653 each complete2,230 pause/status
frames. All primary timeline fields and native PCM match exactly with observation
enabled. The source-bound3130 NES core observes the actual fixed-bank request,
sound-wrapper entry/return and source APU writes without emulated changes.

Current SNES3631 observer3654 likewise reproduces all2,536 frames and native PCM
from control3632 exactly. Both platforms execute the same original request at
F7A8; the next FA54→FA64 wrapper is selected by increasing clock, not by borrowing
the previous tick or fitting waveforms. NES clocks use19687500/11Hz and SNES
master clocks236250000/11Hz, matching their core source constants.

| Measurement | Original NES | SNES3631 |
| --- | ---: | ---: |
| Request → next driver entry |4,323 CPU clocks /2.415390ms|275,796 master clocks /12.841295ms|
| Driver entry → return |1,507 CPU clocks /0.842006ms|15,256 master clocks /0.710332ms|
| Native separated-sound onset |Input offset57|Offset58: FAIL|

The additional request wait is10.425905ms. Original NES request occurs during
VBlank (trace1130 line240), followed by the driver near line31 in the same core
run. The SNES request is at1436 line54, driver at1436 line256, return1437 line5.
These are each core's actual labels, not cross-platform aligned frame numbers.

The two wrapper calls emit exactly the same seven ordered register/value writes:
4004=F0,4004=F0,4005=08,4006=A2,4006=A2,4007=00,4004=FF. Intermediate writes remain
visible, rather than comparing only a final snapshot. A changed-byte control
fails; unit tests reject reordered/incomplete writes, nonmonotonic clocks,
duplicate requests, and missing entry/return. This source equality is not a
claim of identical DSP output, NES analog filtering or physical sound.

Thus the traced original driver is not running too slowly for this cue. It waits
too long before being called. The native onset failure remains; neither a gain
change nor accelerated/duplicated music counters would establish a fix. The
native WAV excerpts are unchanged, with no resampling or time/gain alignment.

## Scheduling constraints before implementation

The old raster experiment is **not** a ready fix. Read
`docs/RASTER-WORKER-EXPERIMENT.md`, `docs/IRQ-PRODUCTION-STATE.md` and
`snes/interrupt_policy.inc`: adapters clear hardware timer enables during
critical sections; simply ORing a timer bit back can lose a missed event.
Original coroutine returns and ordinary interrupt returns have different stack
ownership. A new audio timing path must preserve that distinction, deliver each
sound tick once, retain late/missed-event evidence and keep graphics deadlines.
The current early-audio event token means actually serviced, not merely queued;
do not suppress the existing exit by pretending a deferred job already ran.

Next implementation work should target a steady earlier audio service phase
with explicit recovery across critical sections. First qualify ownership and
once-per-tick behavior, then actual pause PCM onset and unchanged source commands,
gameplay cadence and renderer/DMA paths. Do not treat this one-cue diagnosis as
attribution of every reported physical pop or matched-original gameplay speed.
