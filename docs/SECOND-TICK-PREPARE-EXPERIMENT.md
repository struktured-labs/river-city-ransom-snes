# Second-tick producer deferral: earlier main start, worse scrolling

Rejected for promotion. Candidate716 SHA256
`e0c62f486b8ae0a860b8d93ce02786d4f3fd42615ae0c84a6413b5c0ddc0d7b8`
is default-off and not on Rival. No sound changes, hardware inputs, OBS changes
or restart occurred. The active speed/scrolling/audio goal remains incomplete.

## Mechanism

`--experimental-second-tick-prepare` retains the graphics producer that
otherwise delays the main-loop start after original game tick 2. Only stable,
unpaused, fully faded gameplay with the existing deferred-NMI scheduler armed
participates. Audio remains in its previous position. The exact original
camera store and safe publication happen before the retained producer runs.
Both normal and coroutine interrupt exits have a fallback; the latter masks
NMI explicitly before calling it. No pending pass is overwritten.

Private state: `$1B80` pending, `$1B81/2` scheduled, `$1B83/4` served,
`$1B85/6` fallback. This is an experimental scheduling change, not a reduction
in the amount of graphics work. It is incompatible with the older competing
producer-deferral policies. Disabled716 reproduces parent608 byte-for-byte.

## Executed policy test

`second-tick-oracle-715` passes 102 executed cases and rejects five mutations:
lost pending clear, wrong tick, missing pause guard, broken counter rollover,
and missing fallback service. Cases cover every eligibility guard, preexisting
pending work, direct/service/fallback paths and 16-bit counter rollover.
X/Y, DP, DB and SP are preserved. Original 2 KiB game RAM is unchanged outside
the seven legitimate emulation-call-stack bytes `$01F9..01FF`.

The first fixture714 incorrectly required unused popped return-address bytes
to remain zero; it failed and is retained. The corrected check names the exact
seven-byte stack footprint rather than excluding the entire stack page.
The producer bridge in this fixture is a call-count spy: it does not certify
real graphics deadlines, interrupt races or whole-game performance.

## Actual performance result

Candidate716 normal and renderer captures each complete 8,593 frames and
have identical complete timelines and PCM. The final coroutine mask placement
has the same recorded timeline as initial candidate712. The complete park
renderer audit717 retains long stops, frame boundaries and all visible lines.

| Uniform 2px one/three-frame pairs | East | West |
| --- | ---: | ---: |
| Original NES | 3 | 0 |
| Parent608 | 11 | 18 |
| Second-tick candidate716 | 31 | 19 |

The experiment also introduces four-frame holds. This is a clear failure of
the intended pacing improvement; the policy oracle passing cannot override it.
Different encounters still prevent interpreting full-route frame totals as a
speed ratio. Further background/audio qualification was not treated as a way
to rescue a failed scrolling experiment.

Instruction observation714, bound to initial candidate712 and a complete
normal replay with identical timeline/PCM, shows main starts at lines40–58.
The unchanged parent608 observation650 shows lines52–88. Despite starting
earlier, camera stores still cross the early drawing cutoff. Complete-pair
audits718 retain camera-store lines17–237 versus parent24–232, including the
near-end-of-frame cases and explicitly censored window edges. These ranges
are not a linear speed ratio or evidence that every paired iteration is faster.

The direct caller profile in the parent trace identifies main JSR `$F293`
(sprite construction, target `$EFD4`) at roughly72,218 master clocks per call
over33 observations; actor update caller `$F299` is about200,000 clocks over32.
These are elapsed times including interrupts, not exclusive routine costs.
The next optimization target is the actual sprite-building work, after
separating interrupt time, rather than another producer phase shift.

## Evidence and remaining limits

- `build/second-tick-display-717/`: full actual-render cadence distributions.
- `build/second-tick-timing-718/report.json`: complete main/camera instruction
  pairs for candidate712; parent counterpart `second-tick-parent-timing-718`.
- `build/second-tick-oracle-715/report.json`: executed guard/service matrix.
- `build/second-tick-normal-716/`: complete game capture. Final snapshot has
  3,524 scheduled, 3,523 served, one still pending, zero fallback. This is a
  frame-boundary snapshot, not proof that every intermediate job met a deadline.

564 unit tests pass; `git diff --check` passes. No original-speed, full-scrolling,
acoustic, or hardware qualification is claimed. The independently tested
[noise correction](NOISE-GAME-CORRECTION.md) remains available separately.
