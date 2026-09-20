# Bulk-fill dirty sampling

`build/fill-stride-01` marks ordinary filled tile pages every 32 bytes rather
than every eight. Attribute-containing pages retain eight-byte sampling.
Both logical mirroring aliases still get marked, and queued states remain
preserved. This reduces redundant dirty calls on three of every four pages.

The first implementation selected the stride using a condition flag clobbered
by a load; executed case 16 caught the missing attribute rows. The corrected
explicit branch passes the complete adapter suite, including the mutation
that forces 32-byte sampling on attribute pages. All 94 unit tests pass.

Baseline `build/fill-stride-quality-01/snes` completes in 2096 frames versus
2098 previously. This is a small improvement, not completion of the speed
goal. The quality report remains at `build/fill-stride-quality-01/site`.
No deployment.

## Larger startup cost identified

The retained baseline timeline samples PCs `$8038..$8043` throughout its
first 25 display frames. The bound build labels place these in reset's WRAM
clear loop. Frames 26..44 sample the SPC upload, and original game code runs
by frame 45. These are frame-boundary observations, not exact instruction
profiling, but identify a substantial startup cost independently of gameplay.

Next candidate is a fixed-source DMA clear through WMDATA for the same full
128KiB WRAM range. It must run with interrupts/DMA/HDMA disabled, preserve
the reset ABI and clear the entire region before use. A byte-exact RAM oracle
and truncated-fill negative are required before accepting the faster reset.

Attempting `profile_native --warmup 1` failed its NMI-reset check because it
read power-on WRAM before initialization (first two timeline values are
21845). Do not treat that as a game failure; this profiler currently requires
a post-initialization warmup. The startup finding above uses the authenticated
baseline timeline instead of weakening that check.
