# Noise-channel coverage and clock-table experiment

Follow-up: [the real-game correction and isolation audit](NOISE-GAME-CORRECTION.md)
now exposes this as a default-off build option and tests a whole route. The
results below describe the earlier isolated experiment; its retained failure
has not been waived.

No new game ROM or Rival restart. This is an isolated sound experiment, not
a fix for the reported gameplay pops. The production engine and sender are
unchanged. The experimental table exists only in the new diagnostic tool.

## What prompted this

The actual branded park trace `static-arm-branded-park-618-bus.csv` contains
no writes to `$4011` and no `$400E` short-mode bit. Its noise controls use
constant volume. The historical DMC-level subtraction and short-noise omission
therefore do not explain this particular trace. This is not a full-game claim.

The author archive `build/memblers-source-700.zip` came from
https://membler-industries.com/SNES/2a03-src.zip, SHA256
`5a524d0e608721f705a0c625af6ceb054d0861e0a2508bdd52168773920c7d6d`.
Its noise table maps several NES periods to substantially faster DSP clocks.
The current paired/fast-reset engine retains that table at file offset `$849`.

Clock definitions were checked against the actual local emulator sources and
their upstream primary sources:
[FCEUmm sound implementation](https://github.com/libretro/libretro-fceumm/blob/master/src/sound.c)
and [Snes9x DSP implementation](https://github.com/snes9xgit/snes9x/blob/master/apu/bapu/dsp/SPC_DSP.cpp).
The experimental selection minimizes absolute clock error using nominal NTSC
CPU 1,789,773 Hz / noise period and DSP 32,000 Hz / counter divisor. It is not
a fitted spectral-equality model. The DSP cannot reach the fastest NES clocks
and its noise output, filtering and mixer are not identical to NES hardware.

## Executed coverage

`tools/check_noise_audio.py` assembles and executes both an asset-free NES APU
player and a SNES cartridge using the actual paired/fast-reset SPC engine.
It sweeps all 16 long-mode noise periods, then disable, restart, volume 1 and
volume 0. Each phase is 60 source frames. CPU-side register schedules, ordered
frame coverage and sample coverage are checked; NES writes also have the
existing executed shadow/count oracle. This is not SPC received-byte tracing.

The unmodified engine SHA256 is
`47f9352b56ba20d80ced2d52b17d3c38a85fd8186042022548d34d0333adbdd3`,
matching the live branded 616 manifest. The experiment changes only ten bytes
inside the 16-byte noise table; upload size, instructions and protocol stay
unchanged. Strict preimage checks reject changed or duplicate tables.

Each capture retains stereo WAV, timeline, ROM, receipt and source/tool/core
hashes. Four explicitly synthetic PCM controls detect a dead capture, missing
right output, a 100 ms hole and sound during a mute phase. These do not establish
submillisecond click detection, and are not executed driver mutants.

## Results and retained failure

Final captures: `build/noise-audio-baseline-703` and
`build/noise-audio-clock-703`. Both SNES arms pass all activity, mute, restart
and volume gates. High/low volume RMS ratio is approximately 15:1. Measured
spectral centroids move closer to the executed NES reference at all ten rates
whose table bytes change. Rate 7: about 5745 → 4460 Hz versus NES 3588 Hz;
rate 15: 593 → 331 Hz versus NES 287 Hz. These are spectral centroids, not
fundamental pitches or a perceptual fidelity score.

**The combined report deliberately remains FAIL.** The independent NES
disable phase has a decaying filtered tail: peak 32 in the trimmed measurement
window, exceeding the unchanged silence threshold of 8. Its later 0.4–0.5 s
window is zero. The SNES disabled window is exactly zero. No threshold was
relaxed to make this reference pass; settling behavior needs explicit coverage.
The experiment is not qualified for production or hardware listening yet.

557 unit tests pass, including four new noise tests. The existing pulse
diagnostic also passes (`noise-fixture-pulse-regression-702`). No full-route
speed, gameplay pop, short-mode noise, envelope, length or physical-capture
claim follows from these tests.

## Reproduce

```sh
python3 -m tools.check_noise_audio \
  --snes-core .deps/snes9x/libretro/snes9x_libretro.so \
  --nes-core .deps/fceumm/fceumm_libretro.so \
  --out build/noise-baseline-NEW
python3 -m tools.check_noise_audio \
  --snes-core .deps/snes9x/libretro/snes9x_libretro.so \
  --nes-core .deps/fceumm/fceumm_libretro.so \
  --nearest-clock --out build/noise-clock-NEW
```

Both currently exit 1 because of the retained NES early-mute gate. Next:
separate output-filter settling from transport silence without discarding the
early tail, then compare a full game's same-write noise stem and mixed PCM
before considering a game build or Rival restart.
