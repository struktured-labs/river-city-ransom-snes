# Row-source bank experiment — not adopted

An experimental row converter selected DB `$7F` once per converted row,
using 16-bit indirect reads for its eight attribute and 32 tile fetches,
then restored DB before publication. This replaced repeated long-indirect
bank fetches without changing row budgets or output format.

`build/row-db-test-01` passes the independent 3,840-tile oracle over both
pattern halves, both mirroring modes and both producer budgets. The existing
wrong-attribute-quadrant negative control still fails.

However, baseline `build/row-db-quality-01/snes` remains 2,039 frames and the
extended café/exit route `build/row-db-exit-01/snes` remains 7,635 frames,
identical total durations to the parent. The café and matched room-3 strip
checks pass. This does not prove identical cycle costs, but it does not
demonstrate useful frame-level improvement in either tested workload.

The experimental source changes were removed; the current candidate remains
the dead-mailbox build. Experimental builds/captures stay local for review.
No hardware change, new speed pass or audio improvement is claimed.
