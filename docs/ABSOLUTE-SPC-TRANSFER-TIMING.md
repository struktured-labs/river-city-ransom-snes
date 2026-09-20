# Matched transfer timing including VBlank

`build/transfer-timing-audit-01/index.html` contains matched single/paired
360-frame pulse-script captures, WAVs, execution timelines, complete ACK
traces, per-protocol audits, and receipts. Both protocols run independently
on the stock core and observer. Within each protocol, ROM, full WAV and
timeline hashes match between cores. All 341 data phases are measured;
none are excluded.

| Master clocks, handshake ACK to last byte ACK | Single | Paired |
| --- | ---: | ---: |
| Minimum | 15692 | 14036 |
| Maximum | 18274 | 15142 |
| Mean | 16974.1466 | 14598.1994 |

The paired data phase is 13.9974% shorter on average in this isolated script.
This does not measure the entire publication call, the initial ready wait,
SPC synthesis, game speed, or audible popping. In particular it must not be
reported as a 14% game speed improvement.

## Observer clock

Pinned Snes9x source `7a8878f1306f65594c30b7d86dee41d972c2e495`,
`cpuexec.cpp`, subtracts `Timings.H_Max` from `CPU.Cycles` at
`HC_HCOUNTER_MAX_EVENT`. The observer adds that exact value to a host-only
unsigned 64-bit accumulator immediately before this subtraction. It logs
`accumulator + CPU.Cycles` as a ninth ACK CSV column. Thus normal 1364-clock
lines, odd-field non-interlaced line 240 (1360 clocks), and frame rollover
are handled by actual emulator timing rather than reconstructed frame math.

Concrete additions to the existing ACK observer:

```cpp
static unsigned long long rcr_elapsed_line_clocks = 0;
// Immediately before CPU.Cycles -= Timings.H_Max:
rcr_elapsed_line_clocks += Timings.H_Max;
// Append to each ACK record with %llu:
rcr_elapsed_line_clocks + CPU.Cycles
```

The accumulator is not savestate state. Only fresh-process, uninterrupted
captures are supported; no resets, savestate loads, or core reuse. It does
not alter emulated reads, writes, or cycle counts. The observer binary is
`/tmp/rcr-snes9x/libretro/rcr_absolute_ack_libretro.so`, SHA256
`f508deae21b2b083a2be2e17d35118688b864773697e5e80a6b2836f81ddd4b1`.
The stock core remains SHA256
`2e05b2f9a24293fbcdd030d8c117d067dda9533025896365685078d07a1a22e5`.

`analyze_spc_ack.py` accepts legacy eight-column traces with their restricted
active-line measurements, or nine-column absolute-clock traces. It rejects
mixed formats and backwards clocks. New tests cover frame rollover, a short
line, mixed formats and backwards time. All 138 Python tests pass.

Reproduce with `tools/check_transfer_timing.py --core STOCK --observer
OBSERVER --out FRESH_DIRECTORY`. The runner builds both protocols from the
same current source, verifies signal checks, requires an absolute clock,
checks observer equivalence, and reports the measured difference.

Next: opt-in game integration and matched route/audio audits. The retained
default ROM and Rival deployment have not changed.

## Restored persistent observer (September 16)

The old `/tmp` observer disappeared after the host reboot. The same host-only
accumulator has been restored in `.deps/snes9x/cpuexec.cpp` and built separately:

```sh
make -C .deps/snes9x/libretro -j4 TARGET=rcr_absolute_ack_libretro.so
```

Current observer SHA256:
`d34d78d7d5fe6531436d04251ecb477d96394fb7774eb098260a1c13d0f87f43`.
Current default core SHA256:
`90be653f32f20c4057bea02df1677b4764a76d5b142eb579baebb1e79410bc05`.
These are the current instrumented source builds, not the historical binaries
above. `build/transfer-timing-restored-152/index.html` repeats the isolated
equivalence audit successfully. Complete park captures in
`build/park-stress-snes-150` (default) and `build/park-stress-snes-152`
(absolute observer) have identical 9,412-frame timelines and WAV bytes.
