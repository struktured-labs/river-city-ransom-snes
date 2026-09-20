# Current noise attacks: executed NES state reference

Follow-up: [quality-path controls and a binary BRR prototype](BINARY-NOISE-PROTOTYPE.md)
retain the spectral difference against High/Very High NES references. The new
SPC prototype executes, but its level/spectral regressions block deployment.

2026-09-19. No production-ROM edits, Rival inputs/restarts, or OBS changes.
The previous goal turn improved physical camera-recorder coverage. This turn
adds an executed noise reference and narrows the source of an audio difference;
it does not clear the physical popping or speed/scrolling requirements.

[Native clips and whole-frame waveforms2598](http://127.0.0.1:8766/noise-packet-reference-review-2598/)
and [measured filter contribution2603](http://127.0.0.1:8766/noise-filter-audit-2603/).

## Reference construction and exact limits

All1,238 physical packets retained by2079 use noise control `$30..$3F`, constant
volume and halted length, continuously enabled noise, long mode and zero DMC
registers. Builder2595 verifies that scope before constructing a noise-only
asset-free NES player: one initial enable/length load, then the captured
`$400C/$400E` snapshots each frame. Ignored period bits are retained verbatim.
Unsupported envelope/length/short-mode/DMC/enable changes or missing packets
are rejected, not approximated. Other channels stay disabled.

This is **not original-write recovery**. The LFSR starts cold, initial length
is synthetic, snapshots are VBlank-quantized, and original within-frame timing
is unavailable. Repeated C/E writes do not reset the noise shift register in
the executed local core, consistent with the
[upstream FCEUmm register implementation](https://raw.githubusercontent.com/libretro/libretro-fceumm/master/src/sound.c).
This is an emulator reference, not NES analog-hardware certification.

All1,238 frames and2,479 executed writes pass the shadow/count checks; the
noise length remains active throughout. A physical-store mutant redirects APU
writes to expansion space while retaining shadow/count updates and instruction
length. It reaches the acoustic check and is rejected for silent output.

Fresh SNES stem2596 uses fixture2277, with engine SHA
`c880c1c1c5174305a8a8256809c55d4b6dc44cd21237b019eace5dc902c28a76`,
byte-identical to production2367's extracted SPC. Its whole timeline, game RAM
and final image equal normal2280 on the same core. Host mixer isolation is
verified after ROM load; no game commands or engine instructions change.

## Frozen physical events, not a newly favorable selection

All12 event selections and the single11.306-second lag remain from2290.
Eleven windows lie inside emitted-command coverage; event7 remains excluded.
Each +/-20ms replay window selects every overlapping source frame, then uses
those same whole source frames on both systems. No per-event alignment, phase
fit, sample-rate conversion or volume normalization. Native listening clips
extend15 source frames on either side; exact slices are independently checked.

In all11 windows the SNES spectral centroid is higher: **1.317–1.900 times**
the NES reference. Maximum step/window-peak ratio is higher in9/11 windows;
the other two are retained. NES absolute steps are larger in these windows,
so simply minimizing step size is not a fidelity test. No new numerical
threshold is presented as proof that a physical event is or is not a pop.
The existing nearest-clock noise table is already present in production;
this is not rediscovery of the older uncorrected clock table.

For the strongest physical context, source frames413–416:

| Metric | NES state reference | Current SPC noise |
| --- | ---: | ---: |
| Peak magnitude |5,859|1,599|
| Maximum adjacent step |5,795|2,398|
| Step / peak |0.9891|1.4997|
| Spectral centroid |4,753.25 Hz|9,033.09 Hz|

The five-identical-state steady selection has **zero qualifying frames**.
That empty result is retained, not redefined as a steady-tone pass. These are
rapidly varying combat-noise contexts, not isolated sustained-tone coverage.

## Is the gap introduced by the NES output IIR?

Fresh normal2600 and observed2601 use the same filter-observer core. PCM,
timeline and RAM match exactly; the normal output also exactly equals2595
before reusing its selected callback windows. Auditor2603 reconstructs all
**998,292 samples in1,250 blocks**, including every starting accumulator and
integer coefficient. Both stereo outputs equal the reconstructed result.
A corrupted actual input sample is rejected by the recurrence checker.

The observed NES centroid is already lower than SNES **before** this IIR in
all11 windows. The IIR raises, rather than lowers, centroid by1.5–29.5% here.
In the strongest context it changes4,359.01→4,753.25 Hz, still far below
SNES9,033.09 Hz. Thus this measured gap is not solely caused by the final IIR.
The hook is after NES sample generation/downsampling: it does not separate
noise-generator differences from earlier resampling/filtering. Raw pre-IIR
data is analysis only; listening files retain the actual delivered filter.

Next audio target: separate long-mode noise generation and sample-conversion
differences before choosing a cartridge-side correction. The earlier actual
DSP reconstruction2298 established ordinary noise-state transitions, not
volume spikes, at selected replay edges. Do not suppress legitimate attacks,
remove retriggers, or deploy generic smoothing based only on a lower step score.
The production camera hold and perceptual hardware-popping attribution remain
open, and this work does not substitute audio metrics for full-speed testing.

## Verification and handoff

1,156 unit tests pass (`/tmp/rcr-tests-2604.log`), including seven new tests for
strict noise-state scope, physical-store mutation, source-frame boundaries,
native measurements and same-core observer rejection. Review2598 has99 verified
source bindings,47 artifacts and22 exact native excerpts. Filter review2603
has120 verified source bindings. Both pages were inspected in Chromium.
2597 and2602 are retained preliminary reports whose builder source evolved;
2598 and2603 are the current-source reports.

Read-only Rival check confirms production2367 launcher `RCR-SNES-fa7e249a299c`
still running with saved SNES.CFG unchanged (`066fa49a5cb0…`). No controller,
audio-route or saved-setting mutation occurred this turn. SNAC's last visual
verification remains2588; no new physical-button test is claimed.
