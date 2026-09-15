# Non-perturbing raw APU write observation

The opt-in `RCR_APU_TRACE` hook in `tools/snes9x-debug.patch` observes the
production adapter's `STA $0A00,X` instruction before execution. It inspects
the existing opcode buffer and CPU registers directly, without bus reads or
emulated-cycle changes. Its address/bank filters deliberately target this
adapter, not arbitrary SNES programs or SPC packets.

CSV fields are raw core frame, scanline, CPU cycle, adapter NMI counter, NES
register address, byte value, and CPU PC. Repeated and zero-value writes are
retained. A missing/empty trace must not count as evidence. The parser validates
field ranges and frame ordering; its tests reject invalid and reversed traces.

## Current capture

`build/apu-write-trace-01/snes` captures the unchanged current ROM, SHA
`74fe0decfe571e9f43897ffd54aa914db4ee50e1f7947d3b9e0591f3e53326dc`.
The separate trace core is `/tmp/rcr-snes9x/libretro/rcr_apu_trace_libretro.so`,
SHA `eba03cd7279d0ceaf659c54000ff9a6ab457e2ad35b454a58abda1a67b5536c6`.
The existing core remains byte-identical at SHA
`2e05b2f9a24293fbcdd030d8c117d067dda9533025896365685078d07a1a22e5`.
The complete tracked debug patch passes an apply check against the pinned
original emulator sources.

Compared with `build/left-clip-quality-01/snes`, all 2,035 trace-enabled frames
have identical video hashes, per-frame audio metrics, original-game RAM hashes,
NMI counters, and phase labels. The complete WAV files are byte-identical.
This establishes non-perturbation for this capture, not every possible run.

The trace contains 6,549 writes, up to 23 in one raw core frame. There are 833
register/frame groups with multiple writes, of which 87 contain different
values. These intermediate events are not available from a single end-of-frame
register snapshot. Core-frame grouping is **not** an SPC publication boundary,
so these counts alone do not demonstrate dropped updates or an audio defect.

```sh
python3 tools/analyze_apu_writes.py \
  build/apu-write-trace-01/snes/apu.csv \
  --out build/apu-write-trace-01/analysis.json
```

Trace SHA: `915cffb89b6e4c4ad58cb0e3e21a7adf081cd2c13a0fc77196716b81c1ea10a5`.
The analysis retains all repeated groups and binds the input hash. Next work is
to compare original NES write sequences and actual SPC packet boundaries, not
to assume all same-frame writes must become separate packets. All 63 unit tests
pass. No ROM change, Rival deployment, or new audio-fidelity pass is claimed.
