# CPU writes versus SPC packet bytes

`RCR_AUDIO_BUS_TRACE` extends the optional emulator observer with one ordered
stream of CPU adapter writes (`W`) and packet-port writes (`P`). The packet
filter identifies the sender's `LDA $0A00,Y; STA $2141` instruction pair and
does not include firmware upload. It observes existing opcode/register state,
without executing extra bus reads or adding emulated cycles.

Rows contain kind, raw core frame, scanline, CPU cycle, adapter NMI count,
register/packet index, byte value, and PC. `tools/analyze_audio_bus.py` requires
complete ordered 23-byte packets, rejects interleaved CPU writes, and compares
each known register with the latest preceding CPU write. It independently
accumulates note-start and pulse-period-reload flags between publications.
Initial bootstrap flags are explicitly excluded from that flag comparison.
The command exits nonzero for mismatches or malformed/truncated evidence.

## Current evidence

Capture: `build/audio-bus-01/snes`, using unchanged ROM SHA
`74fe0decfe571e9f43897ffd54aa914db4ee50e1f7947d3b9e0591f3e53326dc`.
Separate observer core: `/tmp/rcr-snes9x/libretro/rcr_audio_bus_libretro.so`, SHA
`274bf2d72cf574113d189c750b9a3aa7a92bcb6672364cab93cde5f044874d7e`.
The updated tracked patch also passes an apply check against clean pinned
emulator source files.

Compared with `build/left-clip-quality-01/snes`, all 2,035 frames have identical
video hashes, per-frame audio measurements, original-game RAM hashes, NMI
counters, and phase labels. Complete WAV bytes are identical too.

The observer recorded 6,549 CPU APU writes and 1,864 complete packets. There
are **zero mismatches** in known register bytes or checked event flags. Eight
CPU writes remain pending at the end of capture; no partial packet is present.

There are 86 register groups with changing values between packets: 38 for
$400C, 23 for $4004, eight each for $4015 and $4000, four each for $400E and
$4008, and one for $4006. These are retained in the analysis, not collapsed
away. Examples include volume $F0 then $F3 before one publication. Such brief
intermediate writes are not automatically evidence of an audible defect.

```sh
python3 tools/analyze_audio_bus.py build/audio-bus-01/snes/bus.csv \
  --out build/audio-bus-01/analysis.json
```

Trace SHA: `7719309d0c9f41f1f24e30498b58f7d649653bcc1e68d4edcd16676609c507d2`.
Negative unit controls detect stale values, missing event flags, missing or
reordered packet bytes, and interleaving. All 66 unit tests pass.

This checks bytes offered to the SPC port, not acknowledgement completion or
the DSP's resulting playback. It rules out stale-register/missing-event-flag
packet formation in this baseline but does not certify original NES write
timing, engine playback, or all gameplay. Next work needs original write timing
and waveform evidence; blindly sending every intermediate write as another
packet is not justified by these counts. No ROM or Rival change was made.
