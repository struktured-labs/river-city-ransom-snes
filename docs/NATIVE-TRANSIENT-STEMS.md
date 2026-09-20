# Physical transients, isolated replay channels, and current engine

Review: <http://127.0.0.1:8766/native-transient-stems-2290/>.
No Rival, controller, OBS or production-ROM changes in this investigation.
The preceding status-only turn revalidated existing splash evidence but did not
advance the goal; this turn adds fresh executed audio evidence and a reusable
same-command comparison and channel-isolation harness.

## Which engine are we actually testing?

Physical logger2025 / replay2080 embeds regular1699's SPC engine
`8fd485c254902365afcee6946aee5347cc23a52ead9705d2a991be7ad0f00472`.
Latest offline speed candidate2242 embeds
`c880c1c1c5174305a8a8256809c55d4b6dc44cd21237b019eace5dc902c28a76`.
The only difference is the already documented receiver-dispatch optimization:
two operand bytes redirect the unmatched receiver poll directly to the existing
timer helper, removing one redundant jump. Both retain the same samples,
five-clock pitch publication, post-publication key-on and triangle release.

`build_dispatch_packet_replay.py` reconstructs that exact guarded patch from
physical replay2080, then requires byte equality to the engine extracted from
the authenticated latest cartridge. Fixture2277 changes only those two bytes
and the player checksum. All1,238 actual physical packets, original player CPU
code, upload length and stream bytes stay unchanged. This is still a cold,
VBlank-quantized diagnostic, not a physical DSP-state restoration.

Fresh onset-core normal/observed pairs2280/2281 and2282/2283 have complete
same-core PCM, timeline, RAM and image equality. Both independently validate
every received packet and raw-DAC PCM; each has243 eligible pulse restarts,
zero wrong first pitches and zero stale nonzero onsets. All128 DSP registers
agree at each of1,238 packet completion signals across engines. Internal
oscillator phase is not claimed equal.

Differences are deliberately retained:19 per-packet DSP write sequences differ
(46,389 versus46,365 writes overall);63 callback boundaries shift by one sample.
Whole WAV sample count, packet contents and host-frame schedule stay equal.
Waveforms differ, as expected from changed receiver timing, but this is neither
an improvement nor a pop-free verdict.

Trace attempt2279 used a core lacking the required voice observer and failed
closed after replay. It is retained and is not qualification evidence. The new
review explicitly rejects different-core normal/observer pairs, even when their
PCM happens to match. Historical2084 used a different core than2081; the fresh
same-core pair provides the missing stronger control. Its normal PCM/timeline
are byte-identical to2081 before reusing the existing fixed alignment.

## What the channel split establishes

Fresh replay stems2284–2287 use only host mixer masks: noise, all-but-noise,
triangle and all-but-triangle. Each complete1,238-packet run preserves normal
timeline/RAM/image exactly and verifies application of every requested channel
option after ROM load. Noise+rest and triangle+rest each reconstruct all
1,703,706 scalar output samples with residuals only0 or1 (integer rounding).
This is measured for this non-clipping replay, not assumed mixer linearity.

The review keeps the twelve strongest physical sample steps, separated by at
least half a second. Only the previous11.306-second fixed lag is used, with no
per-event time/phase/gain fit. Eleven +/-20ms windows lie inside emitted-command
coverage; the32.621438-second event does not and remains unclassified even
though the replay WAV has a trailing tail.

Within each covered window, the largest replay full-mix step selects **one
sample and channel**. All stems are measured at that identical sample, not at
their independent maxima. Noise has the larger contribution in8 of11 windows;
triangle contributes relatively little to these selected edges. For the window
around the strongest physical transient at18.760917s, replay step+2546 consists
of noise+2392 and rest+154; triangle accounts for+154. These are replay values,
not a sample-exact decomposition of the physical step−3849. Ordinary NES noise
attacks can also be sharp. No transient is declared defective or resolved.

The next useful audio investigation is continuous per-voice DSP state around
these retained noise/pulse edges, rather than another triangle mute change or
global smoothing/attenuation. The pause-edge event still lacks captured commands.

## Harness and auditability

All78 listening excerpts are exact native sample slices: physical48kHz and
replay32,040Hz, stereo S16, no resampling/normalization. Fixed-scale waveforms,
signed contributions, nearby physical commands, actual DSP register context,
complete changed write sequences and all exclusions are in the review.
All52 direct source bindings and112 served artifacts were verified; every WAV
slice was compared to its source. A plot was inspected in Chromium (ImageMagick's
SVG renderer incorrectly omitted its clipped polylines, so it was not used as
visual qualification).

Seven new tests cover guarded engine replacement, one-sample stem corruption,
format/length mismatches, command-tail exclusion, nonfinite alignment, same-sample
component attribution, same-core requirements and retained DSP-state/write
differences. Existing full-scale-click/clipping/inserted-silence negative controls
pass on the physical recording. Full suite: **1,094 tests pass**
(`/tmp/rcr-tests-2291.log`); `git diff --check` passes.

Preliminary review2288 predates stronger fixed-alignment binding;2289 predates
the full write-sequence comparison. Both retained;2290 is authoritative.
Intermittent physical popping, full-game original-speed qualification and final
release readiness remain open. No hardware restart was performed.
