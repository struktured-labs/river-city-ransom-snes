# Content-adjusted original-speed validation

The deterministic candidate and NES runs enter gameplay task `$C0` on the
same absolute host frame. The candidate nevertheless reaches the first ALEX
HUD write seven frames later because its original game stream emits four
additional valid tile-address commands (`$2356..$2359`) before the streams
rejoin. Treating that content difference as renderer delay gave a false
performance signal.

`tools/audit_transition_speed.py` compares the unmodified common command
prefix and the post-insertion cadence. It requires at least 40 matching
commands, a 0–2 frame prefix delta, exactly the four observed candidate-only
addresses, an equal `$2023` → `$2043` command gap, and at most one extra
native publication frame. Delayed-publication and slowed-target negative
controls must fail. `build/street-alex-speed-audit-71/report.json` passes:
49 prefix commands, equal four-frame target cadence, and native publication
latency of one frame versus zero on NES.

The separate fixed-state movement probe covers 24 Right frames. Both systems
move 21 pixels; the SNES reaches every changed X position zero or one frame
earlier. The long route reaches the next room 341 host frames earlier under
the fixed input schedule. These are retained in
`build/pause-fast-reset-opt-movement-audit-64` and
`build/pause-fast-reset-opt-route-64`.

This clears the measured school-intro cadence and active rightward movement.
It does not claim every fight, shop, or ending has been speed-matched.

