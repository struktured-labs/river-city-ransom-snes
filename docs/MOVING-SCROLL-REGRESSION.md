# Moving mall camera exposes publication lag

The retained `literal-tail-buffer-01` replay was audited at additional
explicit same-phase, same-room, same-camera checkpoints, without searching
for a favorable alignment. Gallery: `build/multi-scroll-audit-01/index.html`.

| Checkpoint | Logical camera / scroll | Published HDMA scroll | Fixed-strip differences |
| --- | ---: | ---: | ---: |
| mall_right_00 | 5 | 3 | 4152 |
| mall_right_01 | 110 | 108 | 3908 |
| mall_right_02 | 215 | 213 | 3881 |
| mall_right_03 | 0 | 0 | 0 |

Published values come directly from saved SNES WRAM $1C94/95; logical
values come from original $F6/$3D and $DC/DD. Original and port have equal
logical camera values. Visual inspection shows horizontally lagging scenery.
Other checkpoints have small unmasked actor differences (68/74/84 pixels);
those are retained rather than excluded. The old stationary room-3 check
was insufficient to certify moving scrolling.

An experimental NMI-exit refresh, guarded to VBlank or before line 30,
updated future street HDMA bands after the game NMI. `scroll-exit-01` kept
the 7552-frame route but published 4/109/214 at those three checkpoints:
one pixel still behind. Differences fell to 3239/3156/3023, not zero.
This partial fix was reverted; no hardware deployment or fix claim.

The camera audit now supports `--require-match`: it saves the complete audit
then exits nonzero for any requested pixel mismatch. The three moving
checkpoints fail in `build/moving-scroll-regression-01` (exit 1), while
`mall_right_03` passes in `build/static-scroll-control-01` (exit 0). This
does not silently mask actors or loosen pixel thresholds.

Next locate the game's camera writes relative to the original raster split
and the port's publication. NMI-exit timing alone is demonstrably too early
for these checkpoints. Synchronization must preserve the 9-bit scroll and
band timing, not extrapolate an assumed velocity or shift reference images.
