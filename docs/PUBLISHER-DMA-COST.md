# Publisher DMA timing, measured

Host-only `tools/snes9x_dma_trace.inc` records S9xDoDMA entry/exit, including
early returns, without changing emulated state. Separate core
`/tmp/rcr-snes9x/libretro/rcr_dma_cost_libretro.so`, pinned 7a8878f. Exact ROM
is bank-xor-01. Full 7552-frame timeline and WAV in `build/dma-cost-01/snes`
compare byte-for-byte equal to normal `build/bank-xor-long-01/snes`.

Evidence: `build/dma-cost-01.csv` and `build/dma-stage-01.csv`.
At raw frame 6831, NMI entry is line 240/cycle 80 and original-game NMI
entry FF4F is line 254/cycle 88. The interval is 19104 master-clock cycles
(14 full 1364-clock lines + 8); no short/pre-render line lies in it.

| Transfer | Bytes | Observed elapsed master clocks |
| --- | ---: | ---: |
| Prepared tile rows, 7E:4900 to VRAM | 128 | 1072 |
| Prepared OAM, 7E:5000 | 544 | 4520 |
| Background palette | 32 | 264 |
| Four sprite palette groups | 4 × 8 | 4 × 72 |
| Total | 736 | 6144 |

Thus the measured DMA call intervals occupy about 32.2% of publisher elapsed
time. They include transfer-call overhead and any emulated events that occur
inside those calls, not just eight clocks per byte. The remaining 12960
clocks are outside DMA calls; do not equate them to a pure CPU instruction
count without profiling refresh/other events. No CHR-bank DMA occurs in this
particular frame.

The first DMA starts at line 245/cycle 152, over five lines after NMI entry.
That makes pre-transfer CPU scanning/setup a concrete next profiling target.
This measurement does not show that any publication work may simply be
removed: row queues, transition checks, palette/OAM and raster state still
need correct bounded publication.

No game code or Rival deployment changed in this observation.
