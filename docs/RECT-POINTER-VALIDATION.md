# Increment the resolved fill pointer within each page

Current candidate: `build/rect-pointer-02/native-cpu.sfc`, SHA256
`a6d487c10a7555a36f5c0c5d297d497331cc5f069388a5ecefefbf85634e80d0`.

The guarded rectangular-fill path now resolves the physical shadow pointer
once, increments its low byte within a page, and calls the mirroring mapper
again when the logical address crosses a page boundary. Existing guard,
changed-byte, dirty-segment, counter and final-register semantics remain.

| Transition | Outer-loop parent | Pointer increment | Original NES |
| --- | ---: | ---: | ---: |
| Boot/menu | 172 | 170 | 170 |
| Settings | 59 | 59 | 53 |
| Story | 63 | 62 | 54 |
| Street | 486 | 485 | 459 |

Baseline 1980 -> 1976 frames. Boot/menu matches the reference exactly;
the other three speed gates still fail. Dashboard:
`build/rect-pointer-quality-02/site/index.html`.

Executed adapter case 26 additionally crosses $23FF->$2400 in both
mirroring modes, checks all bytes on each side and checks that the unused
physical table retains its sentinel. Removing the boundary remap fails
case 26, as do skipped stores and the wrong attribute-segment stride.
Full adapter suite and all 113 Python unit tests pass.

The full shop-exit route completes 7572 frames. Café menu matches all
17380 fixed pixels/CHR state (`rect-pointer-shop-audit-02`). Room-3 camera
and scroll checkpoint matches all 20480 fixed strip pixels
(`rect-pointer-camera-audit-02`). The audio audit verifies exactly one
packet for each of 7350 completed NMIs with no unfinished tail:
`build/rect-pointer-long-audio-audit-02/index.html`.

Remaining packet gaps are retained: 1:7325, 2:1, 3:4, 4:6, 5:2, 6:1,
8:2, 9:3, 22:4, 32:1. These and the existing three speed failures prohibit
a full-goal completion claim. Synthesis fidelity/random popping, broader
gameplay, and hardware behavior remain unproven. No Rival deployment.

The separate normal-core run `rect-pointer-long-normal-02/snes` matches
the observed run's timeline and WAV byte-for-byte.
