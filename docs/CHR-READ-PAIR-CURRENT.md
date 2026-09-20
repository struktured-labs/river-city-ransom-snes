# Paired source reads on the current cache build

Candidate `build/chr-pair-on-451/native-cpu.sfc`, SHA-256
`71407e8833617f240f0f82190764c248989daa8a6bd81a4322594dd9d1497c73`.
Default-off option `experimental_chr_read_pair` builds on cache candidate 437.
The disabled build `chr-pair-off-457` exactly matches 437. No deployment or
Rival restart. This does not supersede the original-speed release requirement.

An earlier [paired-read experiment](CHR-PAIR-EXPERIMENT.md) lost time on its
then-current baseline and was rejected. This is a new implementation and fresh
measurement on the current interrupt/graphics/audio path, not an inherited pass.

## Implementation

The public decompression reader already masks interrupts across two PPUDATA
reads. With binary arithmetic, increment one, a CHR address, and low address
below `$FE`, both reads use the same physical page. Resolve once, return the
first byte, retain the second as lookahead, and advance the logical address
twice. Keep the existing save/restore and interrupt re-enable sequence.

All other cases take both original buffered reads: decimal mode, increment
32, non-CHR reads, and either page-boundary case. No intermediate buffer
value is externally visible while this critical section is masked. No asset,
game timer or fade counter was changed. The first assembly attempt 450
exceeded a short branch range; 451 uses a conditional long jump to the
unchanged CPU-memory fallback. Its cost is included in measured game results.

## Tests and negative controls

The real adapter fixture now exercises the public source reader for every
selected CHR-bank value at every high page and inversion mode, with both
increment 1 and 32. It checks returned value/mailbox, lookahead, X/Y, source
index and final PPU address. A deliberately stale initial buffer makes an
omitted lookahead update observable. Directed `$FD/$FE/$FF` cases test both
increments across a page; existing cases retain nametable, swapped palette,
source wrapping and status/overflow checks.

`chr-pair-{control,cache}-oracle-455` cross read-pair off/on with cache off/on:
**256 actual cartridges**, each running the adapter suite and 256 selected
bank values. Both matrices reject all six cache mutants. Initial matrices
453 passed before the extra stale-buffer initialization; 455 is the stronger
current result, not a reuse of the old receipts.

`chr-pair-oracle-456` verifies both matrices' complete sources/artifacts and
rejects five paired-read mutants: missing lookahead, missing increment,
ignored stride guard, ignored CHR-range guard, and ignored page-boundary
guard. All replicated runtime banks are patched with checked preimages and
correct ROM checksums. The first three fail case 13; the last two case 15.

Arbitrary decimal and pending-interrupt states are **not** fully covered by
this matrix. It is not a whole-game or acoustic proof. **455 Python tests
pass**, and `git diff --check` is clean.

## Current game evidence

| Check | Result |
| --- | --- |
| Whole-load frames, rooms 1/2/3 | **22 / 30 / 29**, cache-only 23 / 30 / 29; NES 20 / 31 / 30 |
| First visible offset after enable | 8 / 7 / 7; NES 7 / 7 / 7 — still fails |
| Fixed-offset graphics | Room 1 differs only at offset 7; rooms 2/3 match all 40 offsets |
| Background sweep | **849 positions exact**, coverage 259 / 76 / 140 / 374 |
| Scroll publication | No late publications in the new sweep |
| Strict settling gate | Still fails; not relaxed |
| Status numbers | Opening/reopening pass, zero tested-region pixel differences |
| Stable park packet cadence | Pass: no interval above 1.5 frames |
| Audio transport | **9,055 completed-NMI packets**, no unfinished tail or unflushed writes |

Evidence folders: `chr-pair-entry-454`, `chr-pair-background-audit-458`,
`chr-pair-status-audit-458`, `chr-pair-park-audit-454`, `chr-pair-audio-454`,
`chr-pair-neutral-455`. Observer and normal full timelines/PCM match in both
fixed (9,408 frames) and adaptive (8,555 frames) replays. Adaptive total
duration is not a game-speed ratio: changed timing can change encounters.
Long settling values can span an outward/return visit; they are not by
themselves literal freezes, but the unchanged gate remains failed.

`chr-pair-load-cost-457` is a full neutral CPU trace bounded by the original
rendering-off state: room change 2104, rendering enable **2118**, previously
2119 for cache-only. The source-reader, buffered-read and resolver regions
together take **749,128 own-region clocks versus 956,664**, saving **207,536**.
Resolver entries fall 828 to 444; full buffered-read entries 776 to 8. The
source-reader region alone grows because it now contains the inlined reads;
comparing it alone would misrepresent the result. Nested pointer work is not
included in this three-region sum; no waits are subtracted.

## Separate word-fill combination, preliminary only

`chr-pair-word-on-457`, SHA
`56aaf609159b3ce3a77c00dc3825dd5e79e81fdfa48d1117337601658cfcef0f`, additionally
enables the earlier word-fill path. Fixed replay completes in 9,407 frames;
`chr-pair-word-entry-459` gives **22 / 29 / 29** whole-load frames and the same
8 / 7 / 7 visibility failure. It does not improve room 1 further. This exact
combination has not received the full adaptive/audio qualification above and
must not inherit it. Neither candidate is promoted or deployed.

Next: account for the remaining two first-room frames, including the
post-enable main-loop/palette delay; retain speed, scroll and acoustic gates.
Review: `http://127.0.0.1:8766/chr-pair-review-460/`.
