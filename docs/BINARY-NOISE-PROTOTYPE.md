# Binary BRR noise prototype: implemented, not ready for promotion

2026-09-19. The previous goal turn established a current-engine noise-spectrum
difference. This turn tests whether that conclusion survives different NES
reference quality paths, then implements and executes a different SPC noise
source. No game cartridge, Rival controller, saved setting or OBS change.

[NES quality comparison2613](http://127.0.0.1:8766/noise-quality-review-2613/)
and [prototype/full-mix/noise clips2622](http://127.0.0.1:8766/brr-noise-review-2622/).

## The reference-quality control

Fresh Low/High/Very High pairs2605–2610 use the same filter-observer core,
byte-identical NES ROM and physical-state stimulus. Each explicit option is
queried after ROM load, RF filtering is disabled, and the **actual** quality
mode is observed at every filter block. Normal/observed PCM, timeline and RAM
match within each pair. CPU frame/write/count/status observations match across
qualities; their audio sample boundaries remain different and are not fitted.
Explicit Low reproduces reference2595 exactly.

Independent integer reconstruction checks998,292 /998,344 /998,329 samples,
1,250 blocks per quality, using each path's actual accumulator scale. Wrong
quality and corrupted-input controls fail for all three. Quality labels alone
are not claims of original NES analog-hardware fidelity.

The same eleven frozen event windows retain a higher SNES spectral centroid
against **all three** reference paths. For the strongest physical context,
source frames413–416: Low4,753.25 Hz, High3,671.79 Hz, Very High4,454.26 Hz,
current SNES9,033.09 Hz. Thus the gap is not only a Low-path artifact. The
uncovered twelfth physical event remains unclassified. No physical pop cause
or blanket synthesis-fidelity verdict follows from centroid measurements.

## Implemented offline SPC change

`build_brr_noise_replay.py` requires the exact current engine SHA
`c880c1c1c5174305a8a8256809c55d4b6dc44cd21237b019eace5dc902c28a76`.
It changes voice3 from the DSP's built-in multilevel noise to a BRR sample of
the binary long-mode LFSR sequence. Existing noise volume/GAIN handling and
all physical packets remain intact. Sample directory slot5 points to `$4000`;
NON becomes0; a helper publishes pitch for the captured noise-period index.
Both pitch bytes are prefetched before the existing low/inc-F2/high write
sequence. No production-ROM generator or default option is changed.

The sample contains all32,767 LFSR states followed by **one explicitly held
sample**, making32,768 samples /18,432 BRR bytes. Filter0/range12 uses signed
nibbles±4. Total uploaded engine/sample size is33,792 bytes. This is not a
perfect NES-noise emulation: the held loop sample, Gaussian interpolation,
pitch rounding and cold sample phase differ from the original oscillator.
The builder rejects period0/1, short mode, unsupported envelope/length state,
DMC and missing/disabled noise packets rather than silently claiming support.

Fixture2614 is **only a packet-replay cartridge**. Normal2615 executes all1,238
frames/packets. Stems2616/2617 preserve its timeline/RAM/image, and noise+rest
reconstruct its complete full mix with only the existing integer-rounding
residuals. Observed2618 preserves the normal PCM/timeline/RAM/image; every
received packet matches and raw DAC equals native delivered PCM.

At each actual packet completion, DSP SRCN is5, NON is0, and voice3 pitch equals
the new table. All other ready-register values match the parent. Both engines
retain243 eligible pulse restarts, zero wrong initial pulse pitches and zero
stale nonzero pulse onsets. **Matching ready registers does not prove unchanged
music waveforms, oscillator phases or instantaneous noise-pitch latches.**

## Retained regressions: do not deploy

The same whole-source-frame windows are compared; no waveform alignment or
gain normalization is used. The prototype's centroid is closer to Very High
NES in **6/11** windows and farther away in **5/11**. Its noise peaks are only
**50.1–52.7%** of the parent's. Smaller full-mix steps therefore cannot be
presented as a fidelity fix, and event8's full-mix step actually increases
(2,630→2,975). Every measurement and unaltered listening clip is retained.

The first packet starts at host frame74 versus35 with the larger upload;
the39-frame startup delay is explicit, not hidden through audio cropping.
Thereafter every source frame still advances on consecutive host frames.
This is neither full-game timing evidence nor a acceptable release regression.

This implementation demonstrates a cartridge-side alternative to built-in
noise but is not a release candidate. Next synthesis work must address
period-dependent interpolation/aliasing and level calibration with controlled
tone/noise cases before another full command comparison. Loop-seam behavior,
instantaneous noise pitch, other-voice timing, unsupported modes and game
startup/runtime budgets also need qualification. Do not turn this prototype
on in the user's game merely because some sample-step numbers decrease.
Physical popping attribution and the four-frame camera hold remain open.

## Tests, evidence and hardware handoff

1,161 unit tests pass (`/tmp/rcr-tests-2621.log`), including five new tests for
post-load quality delivery/restoration, actual quality/filter reconstruction,
full LFSR-cycle/sample padding and unknown-engine rejection. Quality review2613
has159 verified source bindings,34 artifacts and33 exact native clips; prototype
review2622 has187 bindings,45 artifacts and44 exact native clips. Both were
rendered in Chromium; the prototype's regression notice was visually checked.
Preliminary2612/2620 remain retained;2613/2622 are current-source reports.

Read-only hardware check still shows production2367 launcher
`RCR-SNES-fa7e249a299c` running, saved SNES.CFG hash `066fa49a5cb0…` unchanged.
No physical recording, deployment, restart or controller input occurred.

Reproduce using the bound input manifests:

```sh
python3 -m tools.review_noise_quality_reference --manifest build/noise-quality-review-spec-2611.json --out build/FRESH-quality-review
python3 -m tools.review_brr_noise_replay --manifest build/brr-noise-review-spec-2619.json --out build/FRESH-brr-review
```
