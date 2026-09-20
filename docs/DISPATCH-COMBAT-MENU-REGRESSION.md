# Receiver-dispatch trial: combat and menu regression

Candidate: `ec1c1ca53d6513bcb57d029e92948fde57f522d2e6ba33996deeb43bd7eb1768`
(`build/receiver-dispatch-1916`). This extends the qualification of the
[SPC dispatch optimization](RECEIVER-DISPATCH-TRIAL.md); it makes no further
ROM changes. **Not deployed. Rival and OBS were not modified.**

## Fresh combat captures

[Combat frames, native audio, and every timing outlier](http://127.0.0.1:8766/dispatch-combat-review-1935/)

Eight fresh processes in `build/dispatch-combat-1930` captured 38,092 frames:
NES and SNES, sustained attacks and running jumps, each with observers off/on.
Within every pair, complete timeline and PCM equality pass. Cross-system
encounters evolve independently; these are not equal-work speed measurements.

- Sustained SNES combat: all 1,661 measured loops pass the strict cadence gate.
- Running/jumping SNES: 1,642 measured loops; two room transitions retain
  15-frame (2560–2575, eight NMI ticks) and 27-frame (4177–4204, seven ticks)
  intervals. The strict gate **fails**. These events are not waived.
- Original NES: one three-tick sustained-attack loop; running/jumping has
  three three-tick loops and one 25-frame interval despite a two-tick counter.
  The latter is retained using frame-span/start-spacing checks, not hidden by
  the counter. It is not asserted to match either SNES room transition.
- All seven outlier signatures (policy, system, start/end frame, NMI count,
  frame span, start spacing, room-change flag) equal the previous
  `combat-outlier-review-1817` signatures. Both reviews' source and artifact
  hashes were revalidated. This is unchanged sampled cadence, not unchanged
  complete game state or audio.

The campaign keeps its existing unmodified scenarios, observer controls,
strict timing gates and negative-control unit tests. Each outlier has exact
captured images and native PCM slices without normalization or time fitting.
The campaign page's inherited “current cartridge” heading refers to the hash
shown on that page, **not** to the cartridge running on Rival.

## Fresh menu captures

Four additional captures total 20,006 frames. Existing NES oracles and known
broken SNES negative controls were reused; candidate captures are fresh.

| Check | Result | Evidence |
| --- | --- | --- |
| Present Status, opening and reopening | Both phases exact, including RAM-derived values | [Status](http://127.0.0.1:8766/dispatch-status-review-1936/) |
| Two purchases in the same shop | Ten phases exact; old stuck prompt still rejected | [Repeated purchases](http://127.0.0.1:8766/dispatch-shop-repeat-review-1937/) |
| Pause selector, HELP, cancel, leave, reopen | Nine phases exact; old lingering cursor rejected | [Pause cursor](http://127.0.0.1:8766/dispatch-cursor-review-1938/) |
| YES → NO → YES → NO, confirm NO | Nine phases exact, money unchanged; old stale cursor rejected | [Shop NO](http://127.0.0.1:8766/dispatch-shop-no-review-1939/) |

“Exact” covers each oracle's fixed pixel region, original CIRAM, SNES shadow
and VRAM checks, not the whole frame. Status additionally checks digits
against candidate RAM at both checkpoints. The candidate status screenshot
was inspected: values are visible. All 130 served HTML/JSON/PNG/WAV artifacts
across these five reviews were fetched over HTTP and matched local hashes.

## Decision

The tested menu fixes survive the SPC optimization; no new cadence outlier
appeared in these two combat policies. This does **not** certify full-game
original speed or eliminate nonzero audio pops. Do not promote this build as
release-ready on these results. Next work remains qualified physical audio
testing and investigating the retained transition/rare slowdown cases.

Unit suite rerun: **992 tests pass** in 5.986 seconds,
`python3 -m unittest discover -s tests`, log
`/tmp/rcr-tests-1940.log`. No default engine, graphics, controls, splash assets,
hardware configuration, or prior evidence was changed for this regression.
