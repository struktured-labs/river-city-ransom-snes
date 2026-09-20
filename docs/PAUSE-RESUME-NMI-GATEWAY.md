# Pause/resume deferred-NMI gateway

The deferred gameplay-NMI optimization originally left the main-iteration
latch set when the original `$F289` pause branch skipped the ordinary camera
tail. NMIs arriving after that branch could remain deferred indefinitely,
freezing the blue pause/settings screen.

The builder now retargets only the taken `$F289` branch to the otherwise
later `$F2E7` exit gateway. `deferred_game_nmi_pause_gateway` clears the
camera-bearing iteration marker, drains a pending NMI exactly once through
the existing banked trampoline, and then distinguishes the genuine pause
route from the original outer-loop exit. The unpaused `$F28B..$F2B4` fast
path is byte- and cycle-identical.

`tools/audit_pause_resume.py` requires delivered pause/resume input, NMI/RAM/
video liveness, resumed audio, a drained deferred latch, and zero fallback.
`build/pause-fast-reset-opt-audit-64.json` passes all ten gates. This is a
liveness result, not an audio-fidelity or whole-game performance claim.

