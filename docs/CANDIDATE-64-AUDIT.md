# Candidate 64 audit handoff

ROM: `build/paired-fastrom-deferred-game-nmi-pause-fast-reset-opt-64/native-cpu.sfc`

SHA-256: `a7e363f96d71429a4b68fe77950aed5eeb5f5781c29fd23668ce0b5ab0531c7e`

The consolidated browser entry point is
`build/fast-reset-opt-candidate-audit-73/index.html`. It hash-binds six
complete candidate captures to the ROM and indexes 12 independent gates:
pause/resume, movement, content-adjusted transition cadence, route progress,
mixed and isolated audio, CPU/SPC transport, two scrolling rooms, café menu,
and mall CHR state.

The exact-frame scrolling run tests camera values 5, 110, and 215 in room 2,
then 5, 68, and 131 after crossing into room 3. The fixed background band is
pixel-exact at every stable checkpoint. Both NES and SNES take one frame from
the first logical value to the deterministic second consecutive sample. The
larger actor-bearing strip is retained as a diagnostic rather than silently
masked; actor state differences do not become a scrolling failure.

The dashboard marks this candidate hardware-test ready, not release ready.
The remaining required evidence is an analog/subjective MiSTer listening
pass, broader whole-game coverage, and any user-observed reproduction that
contradicts the automated gates.

