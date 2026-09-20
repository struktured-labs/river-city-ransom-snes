# Alley loading: measured regression and rejected smaller batches

Current Rival cartridge remains `fa882cb61138` (postpublish-keyon-1321).
No deployment, restart, controller input or OBS change in this investigation.
The tested eight- and twelve-row variants are **not release-ready**.

Review: <http://127.0.0.1:8766/alley-budget-review-1385/>. Its 17 published
artifacts were fetched over HTTP and hash-checked. The collage preserves
original frames at rendering-enable +7 for all three rooms and all builds;
the linked reports retain all forty fixed-offset background comparisons.

## Current regression, distinct from scrolling

`postpublish-entry-1371` finds first alley scenery at rendering-enable +8
versus NES +7, and 22 frames after room change versus NES 20. Alley fade
offsets 7/11/15/19 differ; mall and park match all forty offsets. The older
pre-note-start-fix cartridge also fails (`retained-entry-1373`), so this is
not attributed to the newest audio repair.

Separately, `postpublish-render-audit-1372` passes all 7,238 eligible renderer
frames and 6,278 held-camera checks, with zero missing coverage, split scroll
or stale held-camera failures. This does not certify tile content, physical
camera holds, combat timing, or full-game NES-speed equivalence.

## Controlled one-byte experiments

`tools/build_hidden_budget_trial.py` requires the unique guarded state-2
budget immediate in the exact linked producer. Only that byte and the SNES
checksum change. It does not edit original game logic, fade counters,
graphics, SPC code or publication deadlines. The 16-row control1378 is
byte-identical to the parent. All captures use the existing complete
controller-driven route; differing encounters prevent using route length
as an equal-work game-speed benchmark.

| Build | First scenery after rendering enable, rooms 1/2/3 | From room change | From rendering off |
| --- | --- | --- | --- |
| NES331 | 7 / 7 / 7 | 20 / 31 / 30 | 20 / 31 / 30 |
| Current16 | 8 / 7 / 7 | 22 / 28 / 29 | 22 / 29 / 29 |
| Trial8 | 7 / 8 / 9 | 20 / 29 / 30 | 21 / 30 / 31 |
| Trial12 | 8 / 7 / 7 | 21 / 29 / 29 | 22 / 30 / 29 |

Eight rows fixes all alley fade offsets, but regresses mall offsets
7/10/14/18 and park offsets7/8. Twelve rows reduces alley differences to
offset7 and retains exact mall/park fades, but still misses the first-visible
deadline. Moving work before rendering enable cannot conceal a slower load:
room-change and rendering-off anchors remain independently gated.

Artifacts:

- Trial8: cartridge1376, full normal1379 (8,937 frames), entry audit1382.
  SHA `19549a2920313004781861b5e9ec56a5c701ff886e3418b8e6ce14eb6341b63e`.
- Trial12: cartridge1377, full normal1380 (8,860 frames), entry audit1383.
  SHA `f47e6faab0aa533bfd7f1bc0edaa99268f4bb13760e59ab5f4e99a734ddf4781`.

No fresh renderer/audio qualification is inherited by these trials; their
failed room-entry acceptance already prevents promotion.

## Actual interrupt cost

Instruction capture1374 covers frames2408–2436. The complete 8,861-frame
timeline and PCM exactly match current normal1322. Report1384 binds the
trace, cartridge, linked symbols, observer sources and captures.

The first main iteration after alley rendering enable takes 1,012,156
master clocks to reach the fade service. Its actor update includes466,042
clocks in ordinary NMIs; FA9A includes another171,510. First three hidden
producer row phases cost120,400 /120,876 /120,624 clocks, each with16 direct
row calls. Palette work costs2,616 per pass; deferred sprite work is306
for the first two passes. The third must prepare sprites and CHR, costing
15,862 and10,694 respectively. Thus row work, not deferred sprites, dominates
these early native producer calls. Audio publication is separate and costs
28,016–29,350 clocks across the five measured interrupts.

Costs include DMA/events between instruction dispatches, not exclusive CPU
cycles. The five producer phases exactly partition its elapsed duration;
they must not be added to their enclosing bridge/NMI. The last reported NMI
begins after the first fade call and is context, not part of main-to-fade time.

The first profiler attempt failed closed because it expected RTS at JSL
bridges. Those bridges return with RTL; the corrected auditor distinguishes
both and checks stack restoration. Unit tests cover nested short returns,
long bridges, emulation-stack wrapping, missing/duplicate/reordered phases,
patch scope/checksum, ambiguous guards and retained failing review evidence.

## Next work and limits

Reduce measured row work while preserving ownership and graphics readiness,
then rerun total-load, fixed-fade, actual-renderer, main cadence and audio
checks. A different fixed budget alone is not a demonstrated solution.
The earlier paired-row experiment is documented in HIDDEN-DIRECT-PAIR.md;
its helper savings did not resolve its then-current whole-game loading gate.
Do not silently inherit that result as qualification for this cartridge.

The physical audio gaps and previous hardware irregular camera hold remain
unresolved. This study does not claim a new gameplay fix or trigger a restart.
