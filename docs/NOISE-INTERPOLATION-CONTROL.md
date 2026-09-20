# Noise interpolation experiment: improvement and retained failures

No production cartridge change or hardware operation. Current game candidate3065
remains unchanged; this experiment does not diagnose its physical popping.

[Paired native clips, all measurements and retained attacks](http://127.0.0.1:8766/noise-interpolation-review-3115/)
and [actual source-order writes](http://127.0.0.1:8766/noise-source-order-3116/report.json).

## Why another noise experiment

The earlier full-cycle binary BRR sample was too spectrally dark at many noise
periods. Prior held-case reports2645–2647 show that duplicating each binary bit
twice helps, but remains darker than NES. The new experiment varies bit-hold
length while controlling the bit sequence, sample amplitude, engine code,
upload duration, fast-rate fallback and exact packet schedule.

Fixtures3103/3104 use the same first8,192 bits of the original long-mode LFSR,
each held for either2 or8 BRR samples. Both use level±7, source slot5 and a
constant52,224-byte uploaded image. Rates0–5 retain the existing DSP noise;
rates6–15 use BRR and matching doubled/eightfold pitch. Unsupported short mode
is rejected. The sample sequence does **not** complete the32,767-bit LFSR cycle.
Both arms share the same shortened loop, and that limitation is explicit.

This is not a production solution: a full-cycle8x sample would need147,456 BRR
bytes, exceeding all SPC RAM before code/other voices. Streaming or another
representation would be needed to preserve the full sequence at that density.
Pitch quantization and oscillator phase differ between arms; the comparison
is not a sample-exact subtraction of interpolation alone.

## Executed result

Normal3107/3108 and observed3109/3110 each execute all2,220 packets across30
held cases. The two experimental arms have exactly identical timelines and
callback sample bounds; their first packet is at host frame108. Existing parent
begins at35: the extra73-frame upload cost is not a release-acceptable free
improvement. Within each arm, observer-on/off PCM, RAM and image match exactly;
raw DAC equals native delivered PCM. Actual receiver bytes and DSP source,
pitch, volume and GAIN at every noise completion are checked. Both pulse
restarts retain correct first pitches and no stale nonzero pulse onset.

All20 changed-source cases have spectral centroid closer to Very High NES with
8x holds than with2x. Against the current built-in-noise engine, however, only
13/20 are closer; seven regressions remain. The eight fast-rate fallback cases
are not credited as synthesis improvements. These are descriptive spectral
measurements, not an audibility or pop-free gate.

Volume15 examples:

|Noise period|NES centroid Hz|Current engine|8x trial|NES noise/pulse RMS|Current|8x|
|---|---:|---:|---:|---:|---:|---:|
|6|4,148|5,743|3,863|0.843|0.560|0.812|
|9|2,552|3,078|2,306|0.861|0.558|0.811|
|12|1,106|1,567|747|0.865|0.556|0.812|
|15|335|323|119|0.837|0.555|0.810|

Level ratios are measured, not applied normalization. All listening files are
unaltered native slices with no resampling, gain fitting or per-case time shift.
The slowest-rate spectral failure prevents calling this a general fidelity fix.

## The harness caught a hybrid-source attack bug

Both pulse-only cases match sample-exactly between2x and8x. Fallback noise
periods3–5 also match. The two period2 attacks do **not**: each differs for two
sample frames, despite selecting the same built-in noise source eventually.

Actual DSP writes explain a wrong-source exposure interval in the prototype:

|Packet|Left volume tick|Right volume tick|NON=8 tick|Previous NON|
|---|---:|---:|---:|---:|
|145|4,281,890|4,281,899|4,281,928|0|
|1,153|21,478,407|21,478,416|21,478,445|0|

The helper switches from BRR to built-in noise **after** publishing nonzero
volume:38 DSP clocks after left,29 after right. The changed native samples are
133,809–133,810 and671,200–671,201. The prototype's source-order audit correctly
fails. A trace-only ordering control passes after moving source selection
before volume; no repaired cartridge or repaired waveform was executed here.

This is a bug in the experimental hybrid design, **not a newly established
cause of the user's game pops**. The current game engine keeps built-in noise
selected and does not perform these hybrid source changes. A packet-ready
register check alone would miss the transient; the new attack comparison is
therefore retained as a required test for any further hybrid implementation.

## Verification / next action

Four new unit tests verify identical bit prefixes, exact repeat structure,
explicit nonclosing LFSR state, unknown-engine/repeat rejection, prior-source
state, source ordering and missing/wrong source selection. Full suite:
**1,266 tests pass**; `git diff --check` passes. Reports3113/3114 each bind70
sources and91 artifacts, with90 exact native excerpts. Combined3115 binds85
sources and16 artifacts, including15 rechecked clips. Source-order audit3116
binds103 sources. The combined page was opened and visually inspected.

Do not promote these fixtures. Further hybrid work must select/configure the
source before making it audible, preserve or qualify the long noise sequence,
avoid upload/runtime regressions, and recheck the fixed physical-command replay
and full mix. Meanwhile the production built-in-noise path remains unchanged.
Physical audio acceptance still requires a confirmed Bluemage capture path;
Rivalmage remains untouched.
