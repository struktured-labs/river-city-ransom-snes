# Split-byte pulse pitch investigation

Follow-up: [cycle-balanced inline publisher](BALANCED-PITCH-UPDATE.md) avoids
the extra eighteen-clock cost and helper-space overlap, while retaining
unresolved split samples and the new trial's strict callback failure.

September 18, 2026. [Actual pitch plots and unprocessed audio A/B](http://127.0.0.1:8766/pitch-pair-review-1424/).
No game ROM promotion or Rival restart. The running build remains `fa882cb61138`.

## Measured defect, not yet an audible-pop diagnosis

The live pulse publisher writes the DSP's low and high pitch bytes 17 SPC
clocks apart. The DSP fetches those bytes on distinct clock phases; during an
update it can consume a combination that is neither the complete old pitch
nor the complete new pitch. The existing postpublication-KON repair addresses
note starts, not these updates while a voice is already playing.

The new host-only observer records every V4 sample for both pulse voices.
Audit1417 reconstructs all 3,482,203 actual pitch latches from actual DSP
byte writes and the exact V2/V3a read phases. It also accounts for KON startup
forcing the oscillator pitch to zero. Every reconstructed latch and current
register pair agrees. Pitch modulation on pulse1 is explicitly rejected by
this oracle rather than silently approximated.

The unchanged engine produces 108 intermediate-pitch samples, 33 with nonzero
voice output, envelope, and volume and without that voice's noise bit. This
classification is upstream of global mixing/mute and is **not** an audibility
claim. Each event is one DSP sample; no causal link to physical pops or the
previously recorded 19–30ms silences has been established.

Observer neutrality is complete WAV, timeline, RAM, and final image identity
against a fresh unobserved replay. Raw DSP DAC equals delivered PCM exactly.
All 2,512 received packets match the source fixture byte-for-byte at actual
receiver instruction sites. Both runs contain the same 2,906 source frames.

## Default-off prefetch experiment

`tools/build_pitch_pair_trial.py` changes only checked SPC instructions and
verified unused upload padding in a **packet-player** cartridge. It preloads
the high byte before issuing low/high DSP writes, reducing the measured gap
to nine SPC clocks. No new game cartridge was made. Existing note-start and
triangle helpers, upload length, sample data, and player CPU code are retained.

| Same-command replay | Current | Prefetch trial |
| --- | ---: | ---: |
| Pitch-byte pairs | 13,135 | 13,119 |
| Intermediate-pitch samples | 108 | 58 |
| With nonzero voice output | 33 | 19 |
| Wrong first pitch after eligible note starts | 0 | 0 |

The two initialization pairs still take 20 clocks. Transaction counts differ
because publisher execution time changes; this is not a cycle-equivalent
rewrite. The improvement does not eliminate intermediate values.

Executed checker1422 runs the actual original and trial SPC publishers for
both voices and every 11-bit NES period: 4,096 cases, equal final DP RAM and
DSP registers in every case. An executed wrong-high-byte mutant fails 4,082
cases. Active publication costs **18 extra SPC clocks per voice**; muted cases
are unchanged. This checker does not claim all control combinations, a full
CPU-register ABI proof, game scheduling, or hardware validation.

Onset audit1423 retains all403 restart events,402 eligible starts, and zero
wrong first pitches or stale nonzero onsets on both sides. Wrong-pitch and
missing-sample observation controls are still detected. Unit suite:869 tests.

## Reproduction and retained evidence

- Observer: `tools/snes9x_pulse_pitch.inc`, `tools/snes9x-pulse-pitch.patch`.
  Apply on top of the onset observer. Build the separately copied core at
  `.deps/snes9x-pitch-1415`; touch `apu/bapu/dsp/sdsp.cpp` before make because
  the included `SPC_DSP.cpp` dependency was not tracked by the existing build.
- Capture tool: `tools/capture_pulse_pitch.py`. Baseline1416 uses player1328
  and normal1329; trial1419 uses player1418 and normal1420.
- Oracle: `tools/audit_pulse_pitch.py`; baseline1417 and trial1421 retain all
  events, write/read clocks, previous/target/observed pitches and source hashes.
- Executed SPC comparison: `tools/check_pitch_pair_trial.py`, report1422,
  `.deps/snes9x-driver-1093/libretro/rcr_sweep_driver_libretro.so`.
- Note-start regression: `tools/audit_pulse_onset.py`, report1423.
- Review: `tools/build_pitch_pair_review.py`, output1424. The three plotted
  baseline deviations have matching voice, packet, old/new pitch and ordinal
  on the trial. Plots use separate transaction-time origins; audio clips are
  unprocessed and not waveform/phase-aligned. All reports and hashes retained.

Next: determine whether these isolated pitch excursions contribute materially
to audible artifacts, and whether reducing them is worth the scheduling cost.
No perceptual, original-NES-waveform, full-game-speed or physical-audio pass.
The graphics/fade failures in [the deadline trials](HIDDEN-ROW-DEADLINE.md)
also remain open. Controller modes and splash sound were not changed here.
