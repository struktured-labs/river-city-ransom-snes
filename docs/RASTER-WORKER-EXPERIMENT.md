# First opt-in raster worker: failed accounting

`--experimental-raster` now arms a timer at gameplay NMI return, returns to
the game, and dispatches sound plus graphics preparation from timer IRQ.
The boot IRQ entry selects the current mapped bank; the replicated worker
preserves A/X/Y and the sound driver's FB/FC/FD convention. Coroutine NMIs
remain on the previous synchronous path. This is unfinished experimental
code, not a validated scheduler.

WRAM: $1CA2 enable shadow; $1CA3 pending; $1CA4..6 entry pointer;
16-bit $1CA8 scheduled, $1CAA overwritten, $1CAC served, $1CAE late arm.
The initial arm targets line 30; an already-late low vertical counter causes
an arm three lines later and increments the late counter. The late-arm
logic is not yet robust across the 9-bit vertical-counter wrap.

`build/raster-worker-01` completed baseline in **2036 frames** (retained
1956), and long route in **7632** (retained 7552). This is slower, not a gain.
At baseline resume, 1140 jobs were scheduled, 1084 served, 56 overwritten,
61 armed late. At long-route mall_right_07: 6664 scheduled, 6370 served,
294 overwritten, 600 late, none pending.

`tools/audit_raster_service.py` fails the actual long capture (exit 1), while
also checking the accounting identity. Report:
`build/raster-worker-audit-01/report.json`. Its tests distinguish balanced
but lost work from success and reject late deadlines or unserviced work.
All 123 Python tests pass; that does not make this game candidate pass.

Current Snes9x source (`ppu.cpp` NMITIMEN handler, pinned 7a8878f) clears the
IRQ line/transition when both timer-enable bits are cleared. Existing
critical sections use STZ $4200. Restoring the enable shadow therefore does
not guarantee delivery of an event that fell inside such a section. This
is a concrete integration hazard consistent with the missed jobs; exact
per-event attribution still needs tracing. Simply restoring enable bits is
insufficient. CPU masking/pending-event handling must be redesigned without
exposing the shared hardware mailbox or changing coroutine stack shape.

The experiment remains opt-in for further development. Default rebuild
`build/raster-worker-default-01/native-cpu.sfc` is byte-identical to retained
SHA256 `9d72565ce36e59b77343cd9454128b07fec46e38635cded4641b4e0b8f5fca44`.
No moving-camera fidelity, audio fidelity or original-speed pass is claimed.
No Rival deployment.
