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

## Sustained menu timing, 2026-09-15

`benchmark_capture.py --scenario menu-audio` waits for the recognized menu,
then runs 1,800 frames without pressing any buttons. This removes the earlier
Start-transition divergence; it does not align or edit the resulting audio.
Captures are `build/menu-audio-01/{nes,snes}`. The SNES cartridge is
`build/left-clip-01/native-cpu.sfc`, SHA
`74fe0decfe571e9f43897ffd54aa914db4ee50e1f7947d3b9e0591f3e53326dc`.

```sh
python3 tools/analyze_nes_apu.py build/menu-audio-01/nes/apu.csv \
  --capture build/menu-audio-01/nes \
  --snes-bus build/menu-audio-01/snes/bus.csv \
  --timing-phase menu_audio --out build/menu-audio-01/timing-analysis.json
```

All 8,244 original writes match the candidate's first 8,244 writes, without
skipping or realignment. Of these, 8,236 are in the sustained music phase.
After removing one constant 32-frame observer-origin offset, **every one of
those music writes has zero relative frame drift**. First-to-last matched
music write spans 1,793 frames on each system. The candidate has 42 additional
writes at its capture end, explicitly reported as an unmatched tail.

The complete bus analyzer observes 1,906 SPC packets with no last-register or
accumulated-event-flag mismatch; three CPU writes remain pending at capture
end. Original trace SHA:
`5b05899343e2fd818cbe8c0f32c3dc7e7f907146c11ffd27ea4559100dd18465`.
Candidate bus trace SHA:
`226ad188e69a44e1bc399a8afc5e39a01dcda71865e83fc2d0abbdbe43274f29`.

This rules out frame-scale drift of the translated driver's observed write
sequence in this particular uninterrupted menu run. It does **not** test
sub-frame jitter, successful SPC acknowledgement, DSP synthesis fidelity,
gameplay SFX timing, or hardware capture. The next audio check must examine
delivery/consumption timing and rendered PCM, rather than infer success from
correct register values. No production ROM or MiSTer deployment changed.

The timing comparison stops at the first differing write and reports both
unmatched tails. A synthetic delayed-event/extra-write test ensures it cannot
erase a one-frame timing error or silently realign after a mismatch. The
no-input scenario is also tested. All 71 unit tests pass.
