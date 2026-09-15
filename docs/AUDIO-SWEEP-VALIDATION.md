# Pulse sweep period reload

The pinned library's `Sound.asm`, in `detect_changes`, sets packet bits 6/7
when updating the pulse periods under sweep. Our adapter had sent the raw
registers and note-start flags but never those period-reload flags. The latest
game baseline includes sweep-enabled registers, including $94 on both pulses
and $8D/$8B on pulse 2. This omission is relevant to actual game use, though
frame-sampled register values do not identify every audible defect.

The production adapter now flags writes to $4002/$4003 with bit 6 and
$4006/$4007 with bit 7. This tracks actual writes, including zero values and
repeated values. Existing note-start bits remain independent, and mono bit 5
remains clear. Executed adapter assertion 18 covers both pulses, low/high timer
writes, combined flags, and a non-timer write. Removing bit 6 fails case 18.

## Executed audio evidence

```sh
python3 tools/check_audio.py \
  --core /tmp/rcr-snes9x/libretro/snes9x_libretro.so \
  --out build/sweep-contract-01 --sweep-reload
```

The asset-free cartridge enables sweep ($F1) while repeatedly reloading the
period. It follows the existing ~440 Hz, mute, restart, ~880 Hz script. PCM
measurements pass for all four phases, including stereo routing and the
sub-millisecond dropout check. Per-frame telemetry independently checks that
sweep is enabled and the reload-event counter advances as prescribed.

The command also executes an otherwise matching cartridge with reload flags
omitted. Its first three phases pass, but its final phase remains near 440 Hz
instead of the requested 880 Hz, with continuous audio activity. The harness
requires that specific stale-pitch failure, not merely any failure. Its report
is hash-bound from the positive report. This test now runs in CI.

The early `build/sweep-reload-01` exploratory artifact did not yet contain the
assembly probe and is not sweep evidence. Use `build/sweep-contract-01` (or a
fresh run of the command) for the positive/negative pair.

## Game candidate and limits

Candidate `build/sweep-flags-01/native-cpu.sfc`, SHA
`8ef0b2b92bec9954b153ff0978ac4c2381a2e7c82595231be8b72b775d5ed3c4`,
completes the baseline in 2,035 frames, unchanged from the prior build.
`build/sweep-flags-quality-01/site/index.html` passes settings pixels and basic
audio-presence gates but still fails all four transition timing gates.
Adapter controls and 56 unit tests pass. Rival was not changed.

This fixes a reproducible period-update protocol omission. It does not prove
autonomous NES sweep timing, envelope/length/triangle/noise/DMC equivalence,
game music/SFX waveform fidelity, or that every reported sputter is gone.
