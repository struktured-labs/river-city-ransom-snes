# Complete row invalidation by forward block copy

Retained default candidate `build/row-invalidate-01/native-cpu.sfc`, SHA256
`5e9a9346387b97a67ce2e94589ef76ebf14e4aa52672d7877d41578952b1d1d4`.

When the background pattern half changes, the producer seeds flag zero with
1 and performs an overlapping forward MVN over the remaining 127 bytes.
It restores DB and A8 before continuing. This replaces repeated indexed
stores/comparisons/branches without changing which of the 128 flags become
dirty. It does not widen conversion or DMA budgets.

The row fixture now starts with **clean** flags when testing pattern-half
invalidation, and snapshots every first-batch flag before further work.
The independent oracle checks all 128 flags, including expected paired
ready rows. Previously pre-dirty flags could hide an omitted invalidation.
A 126-byte-copy mutation leaves the final flag clean and fails this oracle.
All visible tile words, both halves, mirroring modes and row budgets pass.
Complete executed graphics suite and all 129 Python tests pass.

Baseline remains 1949 frames and long route 7545. Room sequence, café and
stationary room-3 pixel audits pass. Comparing the entire long capture to
publisher-scan-01, **every rendered-frame hash and the full WAV are equal**.
The whole timeline is not byte-identical: native diagnostic fields differ
on 19 frames; original-RAM differences are confined to addresses $01D3..$01EC
(stack area), with no original-RAM differences outside that range. Do not
call this full machine-state equality.

Evidence: `build/row-invalidate-{baseline,long,route,shop,static-camera}-01`,
`build/row-invalidate-oracle-02`. The complete-invalidation negative control
is now part of `tools/check_rows.py`.

This retains an equivalent lower-overhead primitive with unchanged observed
video/audio, not a demonstrated frame-speed gain. Original-speed and moving
scroll requirements remain unmet; no new audio-fidelity claim or Rival deployment.
