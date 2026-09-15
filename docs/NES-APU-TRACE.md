# Original NES audio-register write reference

`tools/fceumm-apu-trace.patch` is an optional observer for pinned FCEUmm revision
`236ccdfc911e84c60fea6b9d0699c2d440a8de14`. It logs the original address/value
before the PSG, DMC, status, and frame-counter handlers modify their inputs.
It does not add emulated bus accesses or CPU cycles. The optional environment
variable is `RCR_NES_APU_TRACE`.

Rows contain host `retro_run` index, absolute NES CPU cycle, address, and byte
value. Host-frame indexing is for a fresh process, as used by the capture
harness; the observer is not a multi-load/reset frame counter. Both repeated
and zero-valued writes are retained. This is reference observation, not a new
NES APU implementation.

## Evidence

`build/nes-apu-trace-02/nes` contains the frame-attributed baseline. It completes
in 1,936 frames and records 6,356 sound-register writes. Every captured video
hash, per-frame audio measurement, original RAM hash, and phase label matches
`build/left-clip-quality-01/nes`; the full WAV files are byte-identical.

The first 269 address/value writes match the current port's raw write sequence
exactly. The next NES write is $4015=$00 at CPU cycle 6,851,946, host frame 231,
the first frame of `open_settings`. The port's sequence still contains a menu
volume write there. Inputs are driven from visual phase recognition, and the
port reaches the menu later. A global sequence mismatch at this point is not,
by itself, evidence of an incorrectly translated sound driver.

Analysis command:

```sh
python3 tools/analyze_nes_apu.py build/nes-apu-trace-02/nes/apu.csv \
  --capture build/nes-apu-trace-02/nes \
  --snes-bus build/audio-bus-01/snes/bus.csv \
  --out build/nes-apu-trace-02/analysis.json
```

The analysis verifies the capture/reference ROM binding, attributes writes to
exact NES input phases, checks frame/cycle ordering and register ranges, and
retains all events. Its sequence comparison does not realign or silently skip
writes. Tests cover repeated writes, phase attribution, invalid ordering, and
an extra event that must break the common prefix. All 69 unit tests pass.

## Reproducibility and limits

The original executable remains SHA
`6ef5a1bbc11f6a836685031ffd75d374e62c0319e1884521cf654ceca75a2a16`.
The separate observer `.deps/fceumm/rcr_nes_apu_frame_libretro.so` has SHA
`7d5bcbc983c9fc7899aef557d86008d4081a1de57989c750a3bc5a724baf2509`.
The frame-attributed trace SHA is
`7219b4655056dcbd2c3853deb5e995deeded80caf87c32384b4baa2211642136`.
The earlier `nes-apu-trace-01` uses a different, cycle-only CSV format and is
not input to the frame-attribution analyzer.

The source checkout was restored to its clean pinned revision after building
the separate observer; the saved patch passes an apply check against it. To
rebuild, apply the patch in a separate checkout at the pinned revision and
build with `make -f Makefile.libretro -j4 TARGET_NAME=rcr_nes_apu_frame`.
Normal reference builds need no observer patch.

This provides the original write-timing baseline needed for further audio
comparison. It is not a music/SFX fidelity verdict or a fix for remaining
sputtering. No ROM or Rival change was made.
