# Executed sensitivity to omitted intermediate NES volume writes

[Native before/after audio and game-context collage3144](http://127.0.0.1:8766/nes-volume-sensitivity-review-3144/).
No SNES cartridge changes, MiSTer operations or OBS access. This is an
intentional NES-emulator audio mutation, not an unmodified sound reference.

## Causal question and selection

The [original driver trace](ORIGINAL-DRIVER-WRITE-COALESCING.md) showed brief
constant-volume zero→nonzero intervals that the SNES final-value packets cannot
fully represent. The new test asks what happens when a restricted set of those
zero writes is actually omitted, without moving any CPU instruction or final
register write. It is not a complete simulation of the SNES snapshot protocol.

Planner3141 selects204 complete zero-volume runs:169 on pulse2 and35 on noise.
Together they contain323 writes, including consecutive duplicate zero writes.
Removing only the last duplicate would leave the earlier mute active and fail
to test the intended omission. Each selected run requires:

- A known preceding nonzero volume with identical upper control/duty bits.
- Constant-volume zero writes with unchanged upper bits throughout the run.
- A later nonzero write with the same upper bits inside the same wrapper call.

All final writes, enable writes, reloads and duty/mode changes remain intact.
The9,298 excluded zero runs retain explicit reasons, including already-quiet
predecessors, changed/unknown control state or no final nonzero in the same
driver call. No qualifying pulse1 run is invented to broaden the result.

Complete selected runs last314–2,389 CPU clocks. This differs from the earlier
314–2,196 range measured from only the last zero immediately before nonzero:
the new duration begins at the **first** zero in each complete duplicate run.

## Execution, not edited PCM

Sibling core3139 adds an opt-in exact schedule at the existing CPU write
dispatch. With no schedule it forwards every write unchanged. With a schedule,
it skips only the listed APU dispatch when frame, absolute CPU clock,
PC-after-operands, address and byte all match. A missing/mismatched target aborts;
the complete execution log must contain every expected suppression and its
final consumed-count marker. The ordinary pre-dispatch write-intent observer
still records every CPU store in both arms.

Core SHA:
`8b0f009643972af6582dcf34dafe19ccf5c55720424ced719fb719cb2a419310`.
Build3139 binds650 sources. Unmodified control3142 exactly reproduces prior3132
execution and native PCM. Suppressed3143 consumes all323 targets and completes
all8,548 game frames.

Between the same-core arms, every nonaudio timeline field, full original RAM
snapshot, video image, input, callback sample count and sample offset is equal.
All37,457 CPU APU-write intents and26,610 exact-PC events have byte-identical
traces, including absolute clocks. No instruction is removed, delayed, inserted
or reordered. The only intended emulated change is omitting those selected APU
dispatches; CPU execution and the final register-write schedule are unchanged.

## Native PCM result

Both recordings contain6,826,754 stereo sample frames at48kHz. No gain,
resampling, waveform alignment or noise-gate processing is applied.

|Metric|Result|
|---|---:|
|Sample frames differing between original and suppressed|439,530|
|Maximum absolute sample difference|5,134|
|Whole-run RMS difference, native S16 units|38.3362|
|Original / suppressed peak magnitude|13,865 /13,865|
|Original / suppressed maximum adjacent step|9,568 /9,569|
|Clipped samples in either arm|0|
|Selected frame-bound windows with PCM differences|189 /204|

Among the204 retained local windows,26 have a larger maximum step after
suppression and27 have a smaller one;151 are unchanged by that metric. The
global maximum changes by just one sample unit. These measurements establish
that the intermediate writes matter to the generated waveform. They do not
support a blanket attribution of the user's pops to omitted mutes, nor do they
show that intermediate writes can safely be discarded.

Frame-bound windows include one complete callback frame on each side. They may
overlap other selected runs or include filter tails; every overlap is listed.
Their changed-sample counts must not be summed as independent per-write effects.
The report separately measures the whole native recording without windowing.

The first three listening examples are selected by shortest, median and longest
source-run duration, before considering PCM differences. A fourth explicitly
shows the largest measured native difference. Each original/suppressed clip uses
the exact same absolute sample bounds. Game-context pictures are identical
between arms; their equality is not an audio-fidelity claim. No subjective
listening or physical-pop verdict is claimed.

## Verification and next work

Seven new tests cover complete duplicate-zero runs, final-write preservation,
unknown/quiet/mode-changing predecessor rejection, exact insertion guards,
complete executed schedules, nonaudio/sample-count comparison, PCM shape/type
validation and signed overflow in step measurement. Full suite: **1,283 tests
pass**; `git diff --check` passes. Review3144 has1,343 checked source bindings,
13 artifacts and eight independently checked native excerpts. Its web page was
opened and visually inspected.

Preliminary plan3138 was invalidated when the unit-test source gained additional
coverage. The source-binding guard rejected attempt3140 before emulation; fresh
plan3141 and captures3142/3143 use the final test source. No prior evidence was
silently overwritten or treated as still authenticated.

The result supports investigating transient behavior at actual SNES note and
volume transitions, but does not yet justify a new high-frequency SPC transport
or generic smoothing. Current3065 packet delivery remains qualified separately.
Original-speed full-game behavior, scrolling coverage and physical audio still
require completion. Bluemage capture routing remains unconfirmed; Rivalmage
remains off-limits.
