# Adjacent ready-row DMA experiment

Candidate `build/row-pair-02/native-cpu.sfc`, SHA256
`8f53fd146777b3a82919e51700a6a8157861b6fef8573b71968f222337f029a3`.
Current source retains this experimental implementation; the previously
validated dead-mailbox ROM remains available unchanged. No hardware deployment.

The parent loading trace frequently drains only three already-prepared rows
per frame after all CHR jobs have finished. The consumer now combines two
adjacent staged rows into one 128-byte DMA when both are ready and sufficient
byte budget remains. It preserves newer shadow dirtiness, retires both initial
transition requirements, and cannot cross slot 127 into the CHR bitmap.
Unpaired rows still use 64 bytes. Existing beam checks and 2048-byte total
VRAM budget remain in force. Timing coverage is empirical, not a full
worst-case hardware timing proof.

| Transition | Parent | Paired rows | Original NES |
| --- | ---: | ---: | ---: |
| Boot/menu | 196 | 186 | 170 |
| Settings | 77 | 67 | 53 |
| Story | 82 | 72 | 54 |
| Street | 484 | 486 | 459 |

Baseline 2039 -> 2011 frames. All four speed gates still fail. The dashboard
at `build/row-pair-quality-02/site/index.html` retains failures; audio-presence
gates are not an audio-fidelity verdict.

Executed video tests pass, including synthetic pixels and existing negative
controls. New case 12 tests all four next-row states, newer-write retention,
insufficient byte budget, and terminal-row protection. Mutations removing
the wrap guard, accepting only 64 bytes for a pair, or losing the newer write
each fail case 12. All 107 Python unit tests pass.

The 7607-frame shop-exit attempt reports no adapter faults, but route inputs
diverge: at `observe_alley_exit`, the original and parent are in room 2,
whereas the experiment remains in room 1/camera 255. The later shop menu
check fails (wrong CHR banks and 14192 differing pixels), and the original
`mall_right_03` camera comparison rejects unequal rooms. These failures
cannot be represented as a successful graphics regression check or dismissed
as harmless without further testing. Candidate reaches room 3 by
`mall_right_07`, but that is not an equal-time comparison.

Next work: isolate single-row overhead/street regression; reproduce café
entry with auditable inputs and compare graphics; rerun audio bus/PCM checks
on the final candidate before promotion. Random audio popping and full-game
original-speed requirements remain unresolved.

## Follow-up: short movement and menu audio

The attempted single-row fast-path reorder (`row-pair-fast-single-01`)
passed the synthetic test and paired-row negative controls but left every
baseline phase duration unchanged. It was reverted; the runtime remains
the `row-pair-02` candidate above.

`row-pair-movement-02/snes` initially failed the old fixed-OAM-slot tracker:
another actor occupies the tail slots starting during Right input. The
revised tracker requires exactly one matching head pair anywhere in the
original OAM array, retains its slot/X/Y each frame, and rejects ambiguous
duplicates. It performs no nearest-coordinate or time alignment. The same
tile, attribute, geometry, room, camera and Y requirements remain in force.
At `row-pair-movement-audit-03/index.html`, all 32 rightward/settling X
positions match the original NES exactly, with 21 pixels displacement.
This still does not certify combat or full-game speed. All 108 unit tests
pass, including unique relocation and duplicate rejection.

`row-pair-menu-audio-audit-01/index.html` retains full PCM and protocol
evidence for boot plus 1800 menu frames. All 1909 completed packets match
the expected length-gated CPU stream and acknowledgements. Five delivery
intervals longer than one frame occur during boot only; none occur during
the sustained menu phase. This excludes missing per-frame packets in this
menu run, not synthesis artifacts or perceived popping. Startup gaps and
review clips remain in the report.
The separate normal-core replay (`row-pair-menu-normal-01/snes`) has a
byte-identical timeline and WAV to the instrumented run, verifying that
this observer did not perturb the measured behavior.
