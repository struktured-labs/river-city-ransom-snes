# Original sound-driver writes and current snapshot transport

[Measured groups, original timing and complete evidence3136](http://127.0.0.1:8766/driver-write-coalescing-3136/).
No game-ROM change, MiSTer access or OBS operation. Candidate3065 remains the
current offline game build; the separate noise prototypes are not promoted.

## Actual original-NES observation

A sibling FCEUmm build adds an optional host-only observer immediately before
the CPU's existing `BWrite` dispatch for `$4000–$4013`, `$4015` and `$4017`.
It records frame, absolute CPU clock, PC-after-operands, register/value and
original game context. It performs no emulated read/write, synchronization or
cycle addition. Clock precision is the interpreter's instruction timing, not
an independently measured physical bus phase.

Build3130 binds649 source files. Core SHA:
`a6f71c4586869d899124d14446c3ac84abc2f9c5192545f442f252e5ac5387ec`.
Normal3131 and observed3132 each complete8,548 frames and match every timeline
field, full original RAM snapshot, video image, input and native PCM sample.
The new unobserved core also reproduces the prior977 execution and PCM. Prior977
additionally requested four host PPU-register fields (`nes_ppu`); these are
absent in3131, explicitly excluded only from that cross-build schema comparison.
All common fields match. No same-core observer comparison drops any field.

There are37,457 actual APU writes. Exact-PC sound-wrapper boundaries identify
7,898 complete calls containing36,691 writes. All766 writes outside those calls
remain in the report, including initialization and transitions. No startup
write is silently attributed to a later driver call.

## What the current port preserves and coalesces

The existing3068/3069 same-core captures authenticate the current game build.
The current DSP audit checks raw-DAC/native-WAV equality, actual received bytes,
complete ready coverage and pulse restart ordering. All8,802 packets agree with
the CPU's final register values and ordered length eligibility; all5,650 traced
event-metadata writes are represented by their required flag bits. No unflushed
CPU writes, final-value mismatch or metadata mismatch is present.

The final-value/event-bit protocol is nevertheless not a timed APU-write stream:

|Population|Original NES wrapper calls|SNES publication groups|
|---|---:|---:|
|Groups|7,898|8,802|
|Writes inside groups|36,691|39,437|
|Same register written more than once|4,210|4,516|
|Same register given changing values|322|377|
|Repeated writes to length/reload or frame-counter registers|531|569|
|Constant-volume zero→nonzero adjacent writes|285|310|

NES groups are exact complete driver calls. SNES groups include all CPU writes
before publication, potentially including bootstrap/transition work outside
the driver. The two games also run different encounters. Group/count differences
are **not** a count of dropped sound-driver calls or missing transport packets.

The most common changing pulse2 pattern is `$F0,$F0,$FF`; both traces also contain
`$B0,$B0,$B5`, `$F2,$F0,$F2` and `$F1,$F0,$F1`. The final snapshot cannot describe
every intermediate volume state. Event bits preserve occurrence but cannot
encode the multiplicity and spacing of repeated same-register side effects.
The report retains same-value repeated reloads rather than treating them as
redundant bytes.

## Original transient timing

Within actual NES driver calls, the285 constant-volume zero→nonzero intervals
span**314–2,196 CPU clocks**, approximately0.18–1.23 ms using the local core's
NTSC CPU clock definition.274 retain identical upper control bits, allowing a
narrow follow-up to isolate volume suppression without also changing duty or
length-halt mode. The other11 intervals remain visible.

Example: driver883, frame1,443, pulse2 `$4004` goes `$F0` at CPU clock42,950,321
then `$F1` at42,952,517, a2,196-clock interval. These are real writes, not a
synthetic zero inserted into PCM. Sound-wrapper entry/return and all other
register writes around the interval are retained.

This establishes a representational difference worth testing. It does not
prove that omitted quiet intervals cause the user's pops or that adding more
SPC packets will help. A new protocol could itself miss graphics/audio deadlines.
The next causal experiment should selectively suppress only those known NES
zero-volume writes while retaining original CPU timing, final values, reloads
and the complete game execution. Compare the resulting unnormalized PCM before
choosing a cartridge-side change. Do not introduce a generic smoothing filter.

## Verification and retained diagnostic failures

Five new tests cover exact observer insertion, malformed/out-of-range writes,
nonmonotonic clocks, wrapper boundary separation, transient duration, repeated
same-value reloads and a meaningful final-byte corruption control. Full suite:
**1,276 tests pass**; `git diff --check` passes. Report3136 binds708 sources and
its published page; the page was opened and visually inspected.

An attempted old sweep-driver audit3133 fails its obsolete assumption that the
ready-instruction pattern is unique in the whole updated SPC image. It was not
relaxed to create a pass; this audit uses the current guarded receiver/DSP
checker already used by the3065 qualification. The first final-byte mutation
also failed to demonstrate sensitivity because it changed an initial byte with
no preceding observed CPU write. The corrected control selects only a register
with an observed predecessor; it now detects corruption. A unit test preserves
that precondition. Failed logs remain in `/tmp/rcr-transport-3133.log` and
`/tmp/rcr-coalescing-3134.log`; neither attempt published a passing report.

Physical audio, whole-game speed and scrolling qualification remain open.
Rivalmage remains off-limits, and Bluemage capture routing is still unconfirmed.
