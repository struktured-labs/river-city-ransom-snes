# Row publication experiments — no new deployment

A read-only Rival process check still shows `RCR-SNES-765052c.mgl`.
Neither experiment below meets the original room-entry/fade target.

## Split low/high planes: functional, not advancing

The opt-in `--experimental-planar-rows` replaces interleaved row snapshots
with 4-KiB low/high planes at `7E3000` and `7E4000`. The producer block-copies
tile bytes, computes packed palette/pattern-half bytes, and preserves queued
aliases. The consumer writes the low and high VRAM ports in separate DMA
passes, restoring address-increment and channel state. Byte budgets and
initial-publication barriers are unchanged. The build manifest explicitly
names the layout and hashes both new include files.

[Functional pipeline oracle](../build/planar-pipeline-oracle-262/report.json):
1,856 producer cases, 72 DMA cases and six rejected mutants. Producer checks
cover all attribute values and alias states. Consumer checks use 16-KiB actual
VRAM readback, CHR budgets, start rows 0/1/126/127, both hidden limits and all
three transition states. Visible publication may stop at its beam deadline;
the oracle requires a legal nonempty prefix when rows can transfer, exact VRAM
for every retired row, unchanged remaining generations, and no final overrun.
It does not demand a full byte-budget drain when VBlank time has expired.

[FastROM conversion timings](../build/planar-row-timing-262/report.json) save
only 672–748 clocks per dirty-alias row against fused interleaved conversion,
and 1,530 for the measured queued aliases. Separate DMA setup adds consumer
cost. The full game keeps visibility at 11/10/11 frames and introduces one
708,898-clock stable park packet interval (about 1.98 nominal frames):
[entry failure](../build/planar-entry-audit-263/index.html),
[park failure](../build/planar-park-audit-263/index.html).

[All 9,412 timeline rows and PCM match the normal core](../build/planar-neutral-load-spans-266/report.json).
This validates observation neutrality, not the design's suitability. Planar
staging is **not advancing**; default remains off. ROM SHA-256:
`9685af12005fa613f7e682990a4766f4350eca65552cb54bb5df6fd46b5bc4ee`.

## Contiguous runs: faster publisher, visibility target still fails

`--experimental-hidden-row-run` keeps the established interleaved format.
Only in forced-blank state 2 may one DMA collect more than two contiguous
ready rows. The run stops at an unready slot, row 127 or the unchanged remaining
byte budget. Newer shadow-write bits and initial-generation requirements are
retained/retired exactly once per row. State 0/1 still choose the pair helper;
an instruction observer verifies this dispatch policy rather than inferring
it from identical final VRAM. The two experimental formats cannot be combined
through the builder until that combination has its own validation.

[Run oracle](../build/hidden-row-run-oracle-270/report.json): **288 real-DMA
cases, three observer-neutral dispatch cases, four rejected mutants**. Tests
include unready holes at 0/31/127, queue wrap, 0/1/2-KiB CHR work and both
publication budgets. Mutants lose a newer shadow, exceed the byte budget,
advance the cursor incorrectly, or invoke runs in state 1.

The new cursor oracle initially missed a real existing behavior: after a batch
exhausts its bytes, the consumer can skip a following unready slot before
finding the next ready row. The original failing run is retained at
`build/hidden-row-run-oracle-268`. The corrected reference model and a unit
test cover the row-127 wrap / row-31-hole case; no production boundary or
queue requirement was weakened to make the test pass.

[Equal-output FastROM publication timing](../build/hidden-row-run-timing-271/report.json)
measures native-video entry through completed VRAM batches, before final
OAM/CGRAM work. Both arms publish the same 4,096 total bytes and have identical
VRAM and generation flags; each has a full-WRAM normal-core observer control.

| CHR bytes within the budget | Old pairs, clocks | Runs, clocks | Saved |
| --- | ---: | ---: | ---: |
| 0 | 104,066 | 75,808 | 28,258 |
| 1,024 | 89,636 | 67,288 | 22,348 |
| 2,048 | 72,012 | 57,696 | 14,316 |

These are controlled publisher costs, not whole-game speed gains.

The [game park packet gate passes](../build/hidden-run-park-audit-267/index.html),
with [all 9,410 timeline rows and PCM observer-neutral](../build/hidden-run-neutral-load-spans-271/report.json).
However, [entry/fade timing still fails](../build/hidden-run-entry-audit-267/index.html):
11/10/11 frames from rendering-enable versus NES 7/7/7, and 27/33/33 from room
change versus NES 20/31/30. Faster isolated publication has not translated into
an improved first-visible-frame result in this capture.

Run candidate SHA-256:
`76bbf4784ecf5de1239a905256aeb9f3bee02f1d77c7dd27c005bf6c6b49ea72`.
It is **not deployed** and does not yet have exact-ROM café/status/pause or
physical-audio qualification. Defaults remain unchanged. Python suite:
**363 tests pass**.

Next investigation: separate the first main-loop/fade-service delay from the
palette preparation-to-publication delay. Do not infer original-speed parity
from the microbenchmarks or the passing stable-park packet gate. Dense scrolling
coverage and complete physical gameplay audio fidelity remain open.
