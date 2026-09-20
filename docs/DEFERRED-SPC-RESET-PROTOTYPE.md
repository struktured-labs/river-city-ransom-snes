# Combine pulse restarts after synthesis updates

`paired_engine(..., reset_notes=True, deferred_reset=True)` is a diagnostic
variant, not selected by game builds. At packet completion it initializes
pending pulse key-on bits from reset $56 AND enable $55 AND 3, using the
otherwise unused $4014 packet slot ($54) in SPC RAM. The inspected original
engine source does not read that slot. Each duty-change path now ORs its
voice bit into pending state instead of writing DSP KON immediately.
At the original synthesis exit, pending bits are masked with enable and
written once to KON, then the original ready loop resumes.

Checked binary changes replace the two six-byte duty KON sequences at
offsets $BF/$1A1 and the synthesis-exit JMP at $33A. New initialization at
SPC $301F is 11 bytes; flush at $302A is 14. Engine size $2C38. X retains
the receiver's value until original synthesis uses it. No game graphics or
runtime timing changes are involved.

Both pulse diagnostics pass tone/mute/restart/pitch checks in
`build/deferred-reset-pulse{1,2}-01`. The fixed-window NES-reference phase
audit passes in `build/deferred-reset-phase-01` and `deferred-reset-phase2-01`.
Pulse-1 repeatability is 0.98998 versus NES 0.99302; no-reset controls remain
below 0.18. This is repeatability, not exact inter-system phase equivalence.

Executed pulse-1 KON trace `build/deferred-reset-keyon-01.csv` has exactly
one post-startup key-on on each expected enabled reset packet, including
initial packet 1. All are at SPC $3035. The prior duplicate legacy $04C5
write on packet 1 is absent. Muted reset packets do not key on. The observer
WAV matches the normal-core WAV byte-for-byte.

Tests check original-image mutation boundaries, both pending-bit writes,
exit jump, size and unchanged default paired behavior. This is not yet
enough for promotion: simultaneous duty/pitch changes after startup,
both voices together, and executed mutants of the merge/flush logic still
need coverage. No default game or Rival change.
