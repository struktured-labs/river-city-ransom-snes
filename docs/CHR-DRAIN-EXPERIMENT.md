# Rejected multi-transfer CHR publisher experiment

The publisher normally stops its CHR search after one transfer. Experiment
`build/chr-drain-01` continued scanning after a successful transfer, retaining
the 2048-byte invocation budget, 1024-byte minimum remaining-budget check,
24-slot scan bound, and existing per-transfer beam preflight.

The full executed video suite passed, including negative controls and exact
synthetic pixels. Baseline capture completed in 2038 frames versus the current
dead-mailbox candidate's 2039. However, individual transitions were mixed:

| Transition | Parent | Experiment | Original NES |
| --- | ---: | ---: | ---: |
| Boot to menu | 196 | 195 | 170 |
| Settings | 77 | 77 | 53 |
| Story | 82 | 81 | 54 |
| Street | 484 | 485 | 459 |

All four original-speed gates still fail. Evidence dashboard:
`build/chr-drain-quality-01/site/index.html`. This does not establish CHR
draining as the dominant loading bottleneck, nor audio fidelity. The
experiment was reverted: the one-frame aggregate gain does not justify
retaining a change that worsens street arrival. No hardware deployment.
