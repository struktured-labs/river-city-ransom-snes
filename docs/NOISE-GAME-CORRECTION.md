# Noise clock correction: real-game comparison

Candidate `811dd01fd64ecc349f72132f87a0a406e96cdec6543555bd04a3ee7cbfec005d`
is built and tested, **not deployed**. Rival remains on `34835f8`. The user's
original-speed gate remains open; this change does not repair scrolling cadence
or prove intermittent pops eliminated.

## Implementation and exact scope

`tools/prepare_audio.py::nearest_clock_engine` is now available through the
default-off `--experimental-noise-clock` native-builder flag. It replaces the
legacy noise clock lookup with nearest nominal NTSC-to-DSP clocks. Same-size
table only: no SPC instructions, transfer protocol, game code or artwork change.
The disabled build is byte-identical to parent608; its branded counterpart is
byte-identical to the current Rival ROM. The candidate differs by ten table
bytes at `$DB11..DB1B` (one unchanged byte within that span), plus two checksum
bytes. The auditor reconstructs the entire expected image and rejects any
other difference. Original and corrected noise generation remain approximate;
see [the isolated experiment](NOISE-CHANNEL-EXPERIMENT.md).

## Executed game evidence

Both normal captures705 execute all 8,934 frames of the same fixed park route.
Every recorded field except audio agrees: rendered pixels, per-frame original
2 KiB game RAM, native timing/monitor fields, inputs, phase transitions and
audio callback sample boundaries. This proves no observed timing/rendering
regression on this route, **not NES-speed equivalence**.

Observer captures707/708 each match their normal captures. Independent physical
receive tracing validates 8,481 complete 23-byte packets (195,063 bytes).
CPU bus, SPC key-on, received-byte and synthesis-completion traces are identical
between builds. Processing ranges remain 161–1,201 SPC ticks. No delivery or
key-on timing change is being credited for the waveform difference.

Host-isolated voice captures709 establish that all sound except the noise
voice is sample-identical across builds. Each isolation differs from the full
mix and is non-silent. The noise voice actually changes. No controller input
or emulator RAM modification is used to isolate sound.

The publication-frame NES replay709 executes the same 38,309 original ordered
APU writes, across five mapper-bank boundaries. Its host mixer retains noise
only; original register writes are not filtered out. Executed write counts,
register shadows, frame/bank pointers and live PCM are checked. Existing
physical-write, empty-frame and missing-bank controls reject their mutants.
The replay is frame-quantized, **not intra-frame cycle-equivalent**.

## In-game acoustic measurements

The selection uses only packet register state: constant-volume noise enabled
at volume at least 2, one stable period over five neighboring frames, with
middle 60% of each frame measured. It does not select by waveform similarity.
382 frames qualify. Means below are spectral centroids, not musical pitches:

| Noise period index | Frames | NES | Old SPC | Corrected SPC |
| --- | ---: | ---: | ---: | ---: |
| 7 | 358 | 3,585 Hz | 5,749 Hz | 4,466 Hz |
| 11 | 21 | 1,641 Hz | 3,096 Hz | 1,801 Hz |
| 14 | 3 | 597 Hz | 1,214 Hz | 454 Hz |

All three observed means move closer to the reference. The three-frame group
is weak coverage and is not a full-game distribution estimate. The remaining
rate/transition cases are retained in the full recordings, not certified by
these steady-frame measurements.

Whole-route maximum sample step is 4,494 → 4,165 and peak 6,850 → 6,826.
These descriptive values are **not a perceptual pop test**. Gameplay pops,
hardware sound quality and complete NES APU fidelity remain open.

## Harness correction and controls

The initial stem captures707 were invalid: Snes9x queried mute options before
ROM loading, then reset its stereo switch. Their PCM equaled the full mix.
They are retained as failed evidence and are not inputs to the passing audit.
`capture_audio_stem.py` now requests one post-load option update. A noise-only
cartridge with noise disabled produces silent PCM and is correctly rejected
by the existing sustained-audio oracle (`noise-stem-disabled-control-709`).
Unit coverage protects post-load update delivery and exact channel masks.

The earlier isolated NES noise test's filtered early-mute tail is still a
documented failing gate. This game audit does not silently relax or replace it.
Its PASS applies only to the explicitly listed patch, execution, isolation and
delivery invariants; `release_ready` remains false.

## Audit and review

```sh
python3 -m tools.audit_noise_game \
  --plan build/noise-game-plan-710.json --out build/noise-game-review-NEW
python3 -m unittest discover -s tests -q
```

`build/noise-game-review-711` has five unnormalized 600-frame park audio clips,
full-route recordings, per-frame selected spectra, matching screenshot pairs,
strict patch checks and input/output hashes. No physical capture or Rival
restart occurred in this work. Next work returns to the known 1/3-frame
scroll-presentation jitter; this independently tested sound correction can be
carried into the eventual qualifying build.
