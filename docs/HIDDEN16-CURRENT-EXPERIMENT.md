# Sixteen-row hidden batch: fade parity, but not advancing

Candidate `build/chr-pair-hidden16-467/native-cpu.sfc`, SHA-256
`1bd26ccad8979f7acce3c3868e372269492d02b19a008cb99eceaecb991bb9ec`.
Only the existing hidden-row budget changes from 12 to 16 on paired-read
candidate 451. No original timer, asset or visible-row budget changes.
**Not promoted or deployed. The comparison baseline remains 451.**

The experiment follows an actual CPU/stage profile: initial hidden row stages
take about 88,000 clocks per 12-row batch while interrupt work competes with
the first main-loop update. A larger batch might finish earlier but can also
starve the main thread longer; its outcome must be measured, not assumed.

## Results

`hidden16-entry-468` gives first visible offsets **7 / 7 / 7**, matching NES,
and **all 40 fixed fade-offset backgrounds in each of three rooms match**.
However, whole loads are **22 / 29 / 29** versus NES **20 / 31 / 30**. The
first room is still two frames slower. Absolute first-room milestones also
move later in the complete replay:

| Candidate | Room change | Rendering enable | First visible |
| --- | ---: | ---: | ---: |
| 12-row baseline 451 | 2104 | 2118 | 2126 |
| 16-row experiment | 2111 | 2126 | 2133 |

The relative fade result must not be mistaken for an overall startup gain.
`hidden16-load-rows-473` measures three large stages at **117,374 / 116,944 /
117,392 clocks**, then a 43,448-clock tail. These observed spans include
DMA/events and are not an equal-work microbenchmark. Full 9,410-frame replay
timeline and PCM match the normal core.

The fresh adaptive sweep completes 8,915 frames with **771 exact sampled
backgrounds**, but `hidden16-background-audit-471` **fails**:

- Room coverage is 259 / **42** / 145 / 325, below the unchanged 64-position
  minimum in the alley.
- One late-publication warning: frame 8559, room 3, expected camera 420,
  published 422. Its actual scanline outcome has not been diagnosed and must
  not inherit another candidate's transient-camera explanation.
- Six strict settling samples fail. The old gates remain unchanged.

`hidden16-status-audit-470` passes opening/reopening with zero tested-region
pixel differences. `hidden16-park-audit-469` passes scoped stable packet
cadence; `hidden16-neutral-469` proves the entire fixed timeline/PCM neutral
and records no late NMI intervals in the observed park window.
`hidden16-audio-469` verifies **9,230 completed-NMI packets**, no unfinished
tail and no unflushed writes. These do not establish pop-free synthesis or
physical audio fidelity. `hidden16-phase-audio-471` offers the complete
same-input park-running phase from NES and SNES without gain/time fitting.

## Actual-VRAM checks

Fresh `hidden16-vram-oracle-470` passes **4,096 executed cases and four rejected
mutants**. All 128 starting rows, both mirroring modes and pattern halves,
budgets 1/2/10/16, and one/two calls with changed source data. It checks the
entire 8,192-byte actual tilemap, source shadow, immutable staging, row
flags/requirements, cursor and both budgets. Negative controls exercise cache
invalidation, quadrant, physical-page key and unconditional stale reuse.
This qualifies the helper's tested states, not every full-game code path or
deadline. 459 Python tests pass.

The fade improvement is retained as evidence, but the scrolling coverage and
publication failures prevent advancing this candidate. Increasing a budget
alone has not met the original-speed requirement.

## Intermediate budgets also did not improve the first load

Fresh fixed replays for 13 and 14 rows (`hidden13-normal-474`,
`hidden14-normal-474`) both complete 9,408 frames. Their entry audits
`hidden{13,14}-entry-476` both retain **22 / 30 / 29** whole-load frames,
**8 / 7 / 7** visibility and the existing failed gates. Candidate hashes:

- 13 rows: `defdcd5004fc872e9863b987e1fb94df155a6988d5053996e3d0efb915728b1f`.
- 14 rows: `061f574997364182f6668bad71ad1f0f19f32986f3048b0d93806c460db91f42`.

Neither has received full scrolling/audio qualification or been promoted.
These results argue for reducing producer/main-thread work, not continuing
to assume a larger per-interrupt budget will fix the remaining delay.
