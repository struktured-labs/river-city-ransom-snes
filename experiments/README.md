# Local performance experiments

## Map signed-shift translation: not retained

`map-shift.patch` applies to source baseline `a978f91`. It replaces the original
C3B9 signed right-shift-by-five loop with five CMP/ROR pairs. Its executed
adapter test uses 25 Python-generated signed-arithmetic vectors with overflow
both clear and set (50 cases), checking result, A/X/Y, carry, zero, sign, and
overflow. A deliberately wrong sign threshold fails case 19.

The experiment passed those executed tests, existing adapter controls, and all
61 unit tests. Candidate `build/map-shift-01/native-cpu.sfc` had SHA
`95afbc2aed28c7dc0b712e1755f103ec4c08671fc8f484fee6c0c6f07801f80b`.
The baseline capture still took 2,035 frames, identical to the unmodified
candidate. Settings and initial street-background pixels passed; all four
transition timing gates still failed.

The 12,000-frame walk retained a maximum NMI interval of 23 display frames,
with long stalled runs of 22/4/11/11 samples—the same lengths as before.
Encounter timing and picture-change counts diverged, so those aggregate image
counts cannot establish a speed gain. No VBlank overrun was detected.

The shorter instruction sequence showed no frame-level improvement in either
measurement. It was removed from production source; the patch preserves the
implementation and tests for audit without adding another active translation
to maintain. The current port objective remains unresolved. No Rival change.

Evidence remains local and ignored by Git:

- `build/map-shift-quality-01/site/index.html`
- `build/map-shift-01/pacing.json`

The saved patch contains source changes only, no ROM or recorded media.
