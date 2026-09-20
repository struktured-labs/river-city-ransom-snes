# Defer preparation on rendering-off writes

Writing a PPUMASK value with both rendering bits clear still immediately
blanks the SNES display and arms transition state 1. It no longer runs the
graphics producer synchronously at that point. Dirty/staged state remains
available to normal NMI-exit preparation or the subsequent render-on write;
render-on snapshot/publication guards are unchanged. This does not disable
all producer work during blanking or enlarge any VBlank budget.

Executed scheduling case 11 now checks that a rendering-off write performs
no producer call and preserves pending/stale row state. A mutant that jumps
back into the old preparation schedule fails case 11. Render-on scheduling,
transition bitmap/stale-row checks, complete adapter/video tests and 103
unit tests pass.

Candidate `build/defer-blank-01/native-cpu.sfc` SHA:
`e1eaca2f9faaa4cc482d227d3e64f3c15017bfa87d4ddc44e8ea44c6edb0ab5c`.
Baseline `build/defer-blank-quality-01/snes` is 2,043 frames versus parent
2,047. Full café/exit route `build/defer-blank-exit-01/snes` is 7,639 frames.
Both fixed visual checks remain exact:

- Café menu: `build/defer-blank-shop-audit-01/index.html`, 17,380 pixels.
- Matched room-3 strip: `build/defer-blank-camera-audit-01/index.html`, 20,480 pixels.

These are small measured load-time improvements, not original-speed or
full-scene equivalence passes. Audio eligibility remains unchanged; remaining
delivery stalls/popping and complete scrolling/speed validation are open.
No Rivalmage deployment.
