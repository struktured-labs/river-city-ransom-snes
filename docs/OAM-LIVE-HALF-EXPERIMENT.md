# Live-half OAM uploads: correct local optimization, not a qualifying game build

Candidate `build/live-half-on-515/native-cpu.sfc`, SHA256
`183473e564d934044f26836b812d909a07045a0b67a3dae8c47dffea3343c325`.
Default-off `experimental_oam_live_half`; requires the existing delta sprite
producer. No Rival deployment/restart or change to game graphics, sound code,
timers or input. Candidate451 remains the prior comparison baseline.

## Exact change

The converter uses 64 of the SNES's 128 sprite slots. Its first generation
initializes all unused Y coordinates to240 and the high OAM table to zero;
subsequent generations only change the first256 staging bytes. The publisher
now optionally uploads all544 OAM bytes once, then only the first256.
The boot-cleared private latch at`$1BF0` is set **after** completed DMA.
All current OAM staging writers were inspected; the option requires the delta
producer rather than assuming the invariant for arbitrary future producers.
Any future high-table/extra-sprite writer must invalidate or revise this path.

`snes/oam_live_half.inc` supplies the production selection/completion macros.
No queue, late-entry or final-batch guards are removed. Default-off build515
is byte-identical to parent `hidden16-word-496`. The source-current enabled
build515 is byte-identical to enabled511 used by the earlier captures.

## Actual OAM and integration tests

`live-half-oracle-513` executes256 generations each with full and live-half
uploads: **512 generations** total. Physical OAM starts poisoned. Every
generation changes all256 live bytes and reads back all544 actual OAM bytes,
including the unused slots/high table. Transfer counts are checked too.
Each live byte cycles through all256 values. Four actual mutant ROMs fail:

- Short initial transfer: count assertion.
- Missing initialized latch: later count assertion.
- Missing physical DMA: hardware readback assertion.
- Wrong source address: hardware readback assertion.

Attempts510/511 had fixture scheduling/bookkeeping errors: the first sampled
completion after only211 generations; the next lacked the standard fixture's
post-completion VBlank heartbeat. Attempt512 passed both positive variants,
then rejected an ambiguous mutation anchor before mutation execution. These
failures remain retained; only513 is the complete positive/negative result.

`live-half-pixel-516` additionally runs the existing complete production
producer/publisher fixture with the feature enabled, exercising sprite-cache
comparisons and exact BG/OBJ pixel output for600 frames. It passes.
483 Python tests pass; `git diff --check` is clean.

## Measured saving, not an assumed game-speed gain

The bound instruction traces in `hidden16-word-late-cpu-503` and
`live-half-cost-518` both retain complete normal-core timeline/PCM equality.
The physical OAM DMA trigger is identified by checked ROM bytes, not a guessed
symbol. Four observed544-byte transfers take4522 elapsed master clocks each;
four256-byte transfers take2138/2138/2178/2138. These are instruction-entry
elapsed intervals including DMA and intervening emulator events, at different
beam positions. Do not treat their difference as matched-phase exclusive CPU
cost or whole-frame speedup. The new latch/setup overhead is outside them.

The parent missed-camera interval was also broken down: its late-VBlank wait
executes once and consumes only232 clocks, not ten idle scanlines. Publisher
work already occupies most of that time. After early sound returns, the
original C5:A003 path consumes25,314 clocks, including two A379 calls of7316
and11,828. Removing a presumed long wait would not solve this sample.

## Fresh game qualification: failed, not promoted

| Check | Exact candidate result |
| --- | --- |
| Fixed route | 9409frames complete |
| Room loads1/2/3 | **22/29/29**, versus parent21/28/29 and NES20/31/30 |
| First-visible offsets | 8/7/7 versus NES7/7/7 |
| Adaptive route | 8806frames, full observer/normal timeline and PCM equal |
| Sampled backgrounds | 670 exact; coverage259/**42**/138/231, below64 in alley |
| Late-publication gate | Fails at frame7566, room3, expected189/published187 |
| Settling gate | 15failures; not individually excused or rematched |
| Present Status | Both entries exact |
| Stable park packet gap | None above1.5frames |
| Observed park NMI intervals | No late intervals in7600–8420 |
| Full audio provenance | **9232 packets**, complete bound write/header/key-on/ready checks |

Reports: `live-half-entry-514`, `live-half-background-audit-514`,
`live-half-status-audit-517`, `live-half-park-audit-517`,
`live-half-neutral-517`, `live-half-spc-provenance-517`. SPC processing remains
161–1201 observed ticks. This is not acoustic or physical-output certification.
The earlier scrolling warning is outside the scoped park timing window.

A separate existing-option trial, `hidden16-word-triple-506`, uses three-byte
sound transport. Its adaptive replay507 completes8702frames and matches758
sampled backgrounds, coverage259/118/94/287, but still fails late publication
(frame8514, expected278/published280) and nine settling samples. It received
no new triple-protocol audio qualification and is not promoted.

The local OAM optimization is retained default-off. It did **not** preserve
the21-frame loading result or solve scrolling in this route. Next scheduling
work should address actual camera/HDMA publication deadlines, including safe
handling of late results, without claiming a helper pass proves game parity.
Review: `http://127.0.0.1:8766/live-half-review-519/`.
