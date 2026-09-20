# Harmonic WUB ending

The user's direction is a constant low note ending in a slower **WUB WUB WUB**,
then stop. The existing55 Hz tail already has three half-second amplitude
pulses. This revision additionally opens/closes the gritty octave's relative
level, rather than just making the whole sound louder and quieter.

Candidate `build/harmonic-wub-trial-2648/native-cpu.sfc`, SHA
`e80a07797ad1547b89158f71e05289c5a46623563b4ff94ca34a6d270533418b`,
is derived from production2367. It changes only the splash SPC payload and
cartridge checksum. Ident pitch/volume automation, samples, echo settings,
graphics, CPU/game code and game sound emulator remain unchanged.

[Before/after audition and collage](http://127.0.0.1:8766/harmonic-wub-review-2650/)
contains exact, unnormalized native emulator clips. The page records its
offline status at generation; a later hardware handoff is documented separately.

## Rival hardware handoff (2026-09-19, 07:37 UTC)

Boot receipt2654 verifies this cartridge and hash-named launcher on Rival,
with saved SNES settings unchanged and the earlier2367 cartridge retained.
[Native hardware audition and recorded boot](http://127.0.0.1:8766/harmonic-wub-hardware-2659/)
includes the new physical audio, emulator before/after, silent boot video,
and the player-selection handoff. The offline2650 page predates this deployment.

Native capture2653/decode2656 reconstructs2,390 complete callback pairs,
1,917,230 stereo48k frames, with exact source/common conversion. HDMI
reacquisition packets and timestamp residuals remain in the report; callback
completeness is not a sampling-continuity or probe-neutrality certificate.
All53 source bindings, seven artifacts and three native audio cuts verify.
The hardware page was visually inspected. Recorder cleanup and unchanged
OBS audio settings are verified; no existing recording/replay was interrupted.

All five physical **tail** checks pass:55.29/55.14/55.19 Hz, peaks146/175/205,
29/30-frame intervals, trough ratios0.201/0.188/0.070, decay and no clipping.
The broader report is **not all-pass**: the pre-existing quiet-slide checkpoint124
measures79.06 Hz versus70.07 Hz expected (12.83% error). The other11 checkpoints
pass. No threshold was loosened, and no subjective timbre approval is inferred.

OSD screenshot `/tmp/rcr-wub-snac-2665.png` confirms **SNAC Yes** without
toggling it. Receipt2666 closes the OSD; final screenshot2667 checks the
player-selection handoff. No physical SNAC-button test is claimed.
The first attempted reviewer invocation2657 used the reduced provenance schema
and failed before creating a report;2659 uses a fresh full OBS status snapshot.

## Synthesis implementation

`tools/build_harmonic_wub_trial.py` inserts a same-size SPC call into the
existing half-volume overtone write. Its helper fits in unused payload padding
at$03B0, below the sample directory$0400. Upload size and sample data do not
change. The note counter selects the old half-volume formula before note144,
then `2*floor(volume²/256)` for the tail. The latter gives a darker trough and
brighter pulse peak relative to the fundamental. Y and the stack are preserved;
the caller uses the returned A for the other stereo channel. This is harmonic
amplitude shaping, **not a resonant low-pass filter**.

The existing bass pitch remains225 (~55 Hz); peaks are commanded at144/174/204,
direct volume becomes zero at219, and the existing echo drains through239.

## Executed evidence

Fresh-process950-frame candidate and current-build captures use the same
Snes9x binary. Review2650 passes all13 gates:

- Captured fundamentals55.34/55.17/55.18 Hz; peaks146/175/206, spaced29/31 frames.
- Deep pulse troughs20.1%/18.0%/7.8% of peak; final decay and clipping gates pass.
- Open-pulse harmonic/bass power is approximately2.2 times the old sound.
  Open/closed harmonic contrast rises from1.91/2.78/1.31 to4.51/4.88/2.33.
  These are fixed-window band-power measurements, not perceived-quality scores.
- All950 graphics/RAM/timing observations match; post-handoff game PCM is exact.
- Actual image pixels, reveal, hold, silence, and game sound bootstrap pass.
- The old recording fails the stronger-harmonic/deeper-motion comparison.

Extra SPC instructions alter individual volume-write timing:143 pre-tail
channel samples differ, maximum61 PCM units, and12 per-frame audio callback
counts differ by one sample (total lengths match). These differences are
retained explicitly, not described as identical slide PCM. No audition audio
is normalized, filtered, time-fitted, or resampled.

Full suite:1,169 tests pass (`/tmp/rcr-tests-2651.log`). New tests exercise all
240 note indexes ×117 volume values through the helper instructions, preserve
Y/stack, check signed-volume safety, restrict ROM edits, reject double-patching,
and reject unchanged/louder-only harmonic controls. The instruction test is
not a cycle-accurate SPC emulator; the separate Snes9x capture executes the ROM.
All25 source bindings, seven artifacts and two exact audio cuts were verified;
the web audition was visually inspected. Subjective approval remains the user's.

## Reproduce offline

```sh
python3 -m tools.build_harmonic_wub_trial --parent build/compact-sub-wub-2367 --out build/FRESH-TRIAL
python3 -m tools.capture_branding_splash --core .deps/snes9x/libretro/snes9x_libretro.so --rom build/FRESH-TRIAL/native-cpu.sfc --out build/FRESH-TRIAL/capture
python3 -m tools.capture_branding_splash --core .deps/snes9x/libretro/snes9x_libretro.so --rom build/compact-sub-wub-2367/native-cpu.sfc --out build/FRESH-BASELINE
python3 -m tools.audit_harmonic_wub --parent build/compact-sub-wub-2367 --candidate build/FRESH-TRIAL --baseline build/FRESH-BASELINE --core .deps/snes9x/libretro/snes9x_libretro.so --out build/FRESH-REVIEW
python3 -m unittest tests.test_harmonic_wub tests.test_sub_wub tests.test_wub_tail
```

This splash change does not resolve or certify the remaining gameplay slowdown,
camera hold, or sporadic gameplay-audio transients.
