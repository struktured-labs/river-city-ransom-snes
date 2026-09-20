# Mirrored-row copy experiment — not deployed

Rival remains on `765052c`. This opt-in optimization does not yet meet the
original room-entry timing target, and its newest combined ROM has not passed
the complete gameplay/menu or physical-audio suite.

## Measured cost and implementation

The [instruction cost receipt](../build/hidden8-row-cost-audit-232/report.json)
covers two hidden-load frames in the eight-row candidate. Each executes eight
mirrored-row copies totaling 30,608 master clocks, about a quarter of the
125,130–125,170-clock row preparation span. The entire observed replay matches
the normal core's timeline and PCM. These elapsed spans include events; they
are not exclusive CPU costs.

`--experimental-alias-word-copy` replaces the 64-byte MVN with 32 native-word
loads/stores using the existing X source and Y destination. It retains the
dirty-only guard, destination-end Y, source-index X, data bank, direct page
and register widths. Queued aliases are not overwritten. Default remains off.

The first four-kernel version was **46 clocks slower** and was replaced:
[retained failed measurement](../build/alias-copy-fastrom-timing-227/report.json).
The revised single-kernel version measures **3,588 versus 3,836 master clocks**,
a 248-clock saving for one dirty vertical row-0 copy with FastROM enabled:
[timing and full-WRAM observer controls](../build/alias-copy-fastrom-timing-229/report.json).
This is a primitive microbenchmark, not a whole-game speed claim.

The [executed oracle](../build/alias-word-full-oracle-229/report.json) passes
160 cases: 20 source rows spanning boundaries, both mirroring modes, and all
four alias states. Every case checks all 8,192 staging bytes and register/state
preservation. Three actual assembled mutants are rejected: wrong destination,
queued-state overwrite and lost data-bank restoration. The host oracle also
has coverage for all 128 source rows. Eight full row-conversion cases with the
12-row hidden budget are retained in `build/alias-word-hidden12-row-oracle-232`.

## Integrated candidates

| Hidden budget + revised copy | First visible offsets, rooms 1/2/3 | Late stable park packets |
| --- | --- | ---: |
| 8 | 12 / 11 / 11 | 1 — FAIL |
| 12 | 11 / 11 / 11 | 0 — PASS |
| Original NES | 7 / 7 / 7 | not an SPC transport |

Both captures replay 9,409 frames. Retained evidence:
[eight-row entry](../build/alias-word-8-entry-audit-231/index.html),
[eight-row park](../build/alias-word-8-park-audit-231/index.html),
[twelve-row entry](../build/alias-word-12-entry-audit-231/index.html),
[twelve-row park](../build/alias-word-12-park-audit-231/index.html).
Both strict entry/fade audits **fail**. Park packet timing excludes loading;
it neither proves acoustic fidelity nor establishes equal combat speed.
Independently evolving encounters prevent attributing packet differences to
the copy primitive alone.

Twelve-row candidate `build/alias-word-12-native-230/native-cpu.sfc` SHA-256:
`4d10b8b8613924cf2d6449fde77d48fbd97693f18740fc9a7fa13f158aca3b3f`.
Eight-row candidate SHA-256:
`51b6733a17250b89c40c2bdab003521d67f27e9d966a02a695cd10bda06f9c58`.

Python suite: **352 tests pass**. No hardware restart for these experiments.
Next: resolve the remaining preparation/publication delay and verify total
room-change-to-visible latency as well as rendering-enable-relative timing.
Moving work before the latter anchor must not manufacture a passing result.
