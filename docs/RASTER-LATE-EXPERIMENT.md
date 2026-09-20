# Rejected line-200 worker experiment

Hypothesis: defer the combined audio/preparation worker until after most
visible rendering, allowing original game camera work to run first.
`build_native.py --experimental-raster --raster-line 200` now permits this
isolated timing experiment (range 1..220; default remains 30). This build
also used the opt-in paired audio transport and FastROM, all six traces.
`build/raster-late-01/native-cpu.sfc` is NOT a retained/default candidate.

Executed long route: 7608 frames, versus paired non-raster 7541. The route
only visits original room IDs 0,1 rather than 0,1,2,3. The explicit moving
camera audit refuses to compare different rooms. Its route failure cannot
be interpreted as a pixel-level scrolling improvement or an isolated speed
comparison across identical game states.

Host-only camera observer, raw frames 6500..7100:
195 E2B1 camera stores, zero before line 32, range line 63..199. This is a
different scene sequence from the reference mall route, so it does not
establish a matched original-camera latency. It does demonstrate that this
late-worker configuration does not generally deliver early camera writes
in the observed interval. Merely moving the existing worker later is not
enough to recover the deadline.

Counter snapshots at mall_right_07: scheduled 4092, served 4091, pending 0,
overwritten 0, rearms 733. Do NOT label the one-job difference lost work:
the current audit omits an in-flight worker state, and a snapshot during
execution can have pending cleared before served increments. Completion
and deadline correctness remain unproven; the route regression already
rejects this configuration independently.

Evidence: `build/raster-late-long-01/snes`, `raster-late-route-01/index.html`,
`raster-late-observed-01/snes`, `raster-late-scroll-01.csv`. Observer full WAV
and timeline are byte-identical to the normal-core capture. No Rival change.

Next timing work should isolate pre-camera main-thread/NMI costs and critical
sections rather than simply pushing the entire sound/graphics worker later.
