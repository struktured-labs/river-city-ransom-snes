# Loading work: paired rows and word-fill experiments remain unpromoted

The working comparison baseline remains sound-commit candidate 418
(`711681c49ca025d776bd546026328498dd9ddb7b5c2836ab830f8f132f5c4168`).
Neither experiment below resolves the first-room loading gate. No hardware
deployment or Rival restart occurred. Broader speed, scrolling and acoustic
acceptance remain open; a helper pass is not a release pass.

## Current, observer-neutral load profile

`sound-commit-room1-first-426` and `sound-commit-room1-second-426` profile the
actual first two main iterations after rendering enable. All 9,408 timeline
rows and PCM match the normal core. The first iteration's actor update has
236,892 clocks outside ordinary NMIs; the second has 175,488. The second
sprite-list call has 85,858 such clocks. These include memory/events and are
not exclusive opcode timings. Fade calls remain in their original order.

`sound-commit-load-cost-434` additionally profiles the rendering-off window,
frames 2104 through 2119, anchored to game state rather than selected images.
Its complete CPU-observed replay also matches normal timeline/PCM.

| Helper region | Entries | Own-region elapsed master clocks |
| --- | ---: | ---: |
| Rectangular decompression fill | 147 | 763,244 |
| Literal bytes | 54 | 239,722 |
| Compressed source byte | 388 | 388,616 |
| Page fill | 3 | 253,050 |
| Buffered PPU read | 776 | 264,080 |
| CHR address resolver | 828 | 414,928 |

These regions exclude time in callees outside their address range. They do
not subtract original waits or imply NES-equivalent work. Source reading and
mapping are substantial remaining targets; earlier isolated optimizations
must be retested in this current path, not assumed to improve it.

## Guarded two-row direct DMA

Default-off `experimental_hidden_direct_pair` requires the existing hidden
high-byte cache. In transition state 2, an even tile row can batch its odd
neighbor only if both row/scan budgets allow it, the neighbor is exactly
dirty/unqueued, and both aliases are either exactly dirty or both ineligible.
Mixed dirty/queued aliases fall back to scalar handling. Both rows share the
same attribute quadrant. A common 32-byte block move duplicates their tile
high bytes into scratch `$7E55A0..55DF`; two 64-byte plane transfers replace
four 32-byte transfers per destination pair. Forced blank remains mandatory.
Cursor, scan budget, conversion budget, requirements and immutable staging
retain the original outcomes. No game timers or graphics are changed.

Candidate `hidden-pair-on-428`, SHA-256
`66ac2e712829468ccb670c80a9770cf1a2e653468ec67a13350c09d97c40d20f`.
Disabled build `hidden-pair-off-427` exactly matches candidate 418. Initial
prototype 427 exceeded the production code bank by 35 bytes; its two simple
fixture passes are not production qualification. The smaller common-copy
implementation is the one tested below.

`hidden-pair-oracle-432`: **6,144 executed cases and six rejected mutants**.
Every starting row, both mirroring modes and pattern halves, budgets 1/2/12,
mixed/all-dirty aliases, and one/two producer calls with changed source data.
Checks all 8,192 actual tilemap VRAM bytes, all row flags/requirements, source,
immutable staging, final cursor and both budgets. Mutations cover an invalid
quadrant pair, budget overrun, missing high-byte duplication, incorrect DMA
length, missing extra budget accounting, and overwriting a queued alias.

The first matrix 429 exposed a **test coverage gap**: its mixed-alias mutant
started on the wrong parity and survived. The corrected case starts at row 1
and actually reaches the unsafe branch. Fresh full matrix 432 rejects it;
429 remains a failed run, not counted as a complete qualified matrix.

`hidden-pair-timing-434` measures eight equal-output twelve-row stages:
**6,192–8,692 clocks saved**. Both scalar and paired arms independently pass
the VRAM oracle; each observer's full WRAM equals normal execution.

Actual game stages are not uniformly faster: room-1 hidden stages take
85,154 / 85,114 / 85,590 / **92,058** clocks, versus baseline
87,890 / 88,320 / 87,890 / 88,762. The mixed/scalar tail can cost more.
`hidden-pair-load-rows-436` retains every observed stage and proves all 9,408
timeline rows and PCM neutral. The park-only stage audit cannot analyze this
room-1 observation window; its failed invocation was replaced with the
appropriate load-stage audit, not a relaxed park check.

`hidden-pair-entry-430` still fails: first scenery 8/7/7 versus NES 7/7/7;
whole loads 24/30/29 versus 20/31/30. Room 1 differs only at fade offset 7;
rooms 2/3 match all 40 offsets. `hidden-pair-park-audit-430` passes scoped
packet cadence. `hidden-pair-audio-430` verifies all 9,223 completed-NMI
packets, without unfinished tail or unflushed writes. Neither establishes
pop-free audio. No fresh adaptive scrolling/status qualification is claimed.

## Existing word-fill path, freshly exercised

The earlier rendering-off profile motivated retesting the existing disabled
`experimental_word_fill`, without combining it with paired rows. The adapter
fixture builder now exposes this option. Candidate `word-fill-on-433` is
`7e484301f25bd11a812507f42f49e73f0f212d8095b8fefd8214dd4d8d633b88`.

`word-fill-oracle-436` runs the real adapter suite with scalar and word fills.
Case 16 checks every byte of an attribute page, four aligned pages, zero as
256 pages with wrapping, dirty flags and return state. Removing the eighth
word from each unrolled group fails case 16. The first report wrapper 435
incorrectly expected a success-style receipt for the rejected mutant; 436
binds its actual failure log and RAM instead. No claim of all-input coverage.

`word-fill-entry-434` still fails: first scenery 8/7/7 and whole loads
**24/29/29**. The middle load is one frame shorter, but the first is unchanged.
The total fixed replay is 9,407 frames; that is not a whole-game speed ratio.
`word-fill-neutral-434` proves normal/observer timeline and PCM equality.
Scoped park packet cadence passes, and `word-fill-audio-434` verifies all
9,043 completed-NMI packets with no unfinished tail or unflushed writes.
Enemy/game state is not asserted identical between different ROM timings.

Both new options remain disabled in the comparison baseline. 451 Python tests
pass and `git diff --check` is clean. The next experiment should target the
measured decompression/source-address cost, not merely increase hidden work
budgets or alter original fade counters.
