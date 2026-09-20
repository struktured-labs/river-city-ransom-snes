# Current speed candidate: fresh menu/status regression

All four fresh captures use compact-pair2242, SHA
`f7f8e725acaaef5592ededba9149ce17e1d7a43767a8deae739f825270c6c829`.
The rejected centered-pulse audio trial is not included. No hardware change.

Subsequent deployment: [combined2367](SLOW-WUB-TAIL.md) now runs this gameplay
candidate plus the separately handoff-tested55 Hz splash on Rival. The menu
results below remain emulator regressions, not physical menu test results.

| Check | Frames | Result and review |
| --- | ---: | --- |
| Present Status opening/reopening |2537|[Both phases exact, including RAM-derived digits](http://127.0.0.1:8766/compact-pair-status-review-2362/)|
| Pause selector, HELP, cancel, close, reopen |2285|[Nine phases exact; old cursor mutant rejected](http://127.0.0.1:8766/compact-pair-cursor-review-2364/)|
| Two purchases in the same shop |7821|[Ten phases exact; old stuck prompt reproduced](http://127.0.0.1:8766/compact-pair-shop-repeat-review-2363/)|
| YES→NO→YES→NO, confirm NO |7347|[Nine phases exact; old stale cursor reproduced](http://127.0.0.1:8766/compact-pair-shop-no-review-2365/)|

These19,990 freshly executed frames reuse the existing original-NES oracles
and known-broken SNES controls. They do not reuse older candidate captures.
The current Present Status screenshot was inspected: numeric stats are visible.
"Exact" means each existing oracle's declared image region, nametable/shadow,
VRAM and state checks, not every pixel of an independently encountered game.
Original reference/broken/candidate hashes remain in each review's report.

The [load-counter study](LOAD-COUNTER-COMPARISON.md) separately establishes
that the remaining alley transition has original-speed frame timing and
like-for-like game counters. The old strict report is retained. Together these
remove two qualification uncertainties without changing gameplay or hiding
failures. They do not certify physical speed, worst-case graphics deadline,
all scenes, or pop-free audio. Full unit suite is1,116 passing
(`/tmp/rcr-tests-load-counter-2357.log`); `git diff --check` is clean.

Next hardware candidate should retain2242's prior audio engine, not DC2319.
Integrating the separately tested55 Hz splash requires its own splash/game
handoff check. Do not claim it is running on Rival until upload, launch and
physical capture receipts prove that.
