# Publish audio after the original NMI sound update

Current candidate `build/audio-exit-01/native-cpu.sfc`, SHA256
`e315925f2ed76d141d5d1203e93c6e7af602d34e217c21352eac9f0d4a0f92a0`.
No Rival deployment. This changes CPU packet scheduling, not the SPC engine.

Previously `publish_video` sent audio at NMI entry, before the original
game's sound update. Audio publication is now a separate native bridge,
called by both original NMI exit adapters, before graphics preparation.
The bridge preserves the emulation-mode caller's registers/status/DB/DP,
applies the existing length-eligibility mask temporarily, restores raw
enable state, reports timeouts, and clears event flags after transmission.
The entry consumer no longer sends audio. Full raster IRQ emulation remains
unimplemented: gameplay sound is still serviced at the adapted NMI exit.

| Transition | Parent | Exit publication | Original NES |
| --- | ---: | ---: | ---: |
| Boot/menu | 177 | 177 | 170 |
| Settings | 62 | 62 | 53 |
| Story | 64 | 64 | 54 |
| Street | 487 | 479 | 459 |

Baseline total 1990 -> 1982. Boot/menu and street pass the unchanged 5%
speed tolerance; settings/story fail. Passing tolerance is not exact
original speed. Dashboard: `build/audio-exit-quality-01/site/index.html`.

The full `traversal-shop-exit` run completes in 7578 frames. Every one of
7335 completed NMIs has exactly one packet, in order, with no missing or
duplicate NMI identifiers and no unfinished tail NMI. Packet contents and
SPC acknowledgements pass. The audit now explicitly enforces contiguous
one-packet-per-NMI coverage, permitting only one documented unfinished NMI
at the capture boundary; unit controls reject holes, duplicates, ordering
errors and unbound tails. All 113 unit tests and the adapter suite pass.

Audit: `build/audio-exit-long-audit-01/index.html`. Multi-frame delivery gaps
remain: 1:7310, 2:1, 3:4, 4:5, 6:1, 7:1, 8:1, 9:1, 10:1, 11:4, 22:4,
32:1. This is not a popping/fidelity pass.

Ordered raw-write-to-next-packet NMI-counter deltas further verify the
scheduling change. In the parent route all 32490 published writes have
delta 1, with eight unflushed tail writes. In the exit-publication route,
30311 writes have delta 0 and 2104 have delta 1, with no tail writes.
Writes outside the NMI can still wait for the next NMI. These are counter
deltas, not sample-exact latencies, and the runs have different lengths.

The café menu still matches all 17380 fixed pixels and expected CHR banks
(`build/audio-exit-shop-audit-01/index.html`). The room-3 `mall_right_03`
checkpoint matches all 20480 strip pixels, camera and scroll registers
(`build/audio-exit-camera-audit-01/index.html`). These checks are scoped,
not full-game scrolling or combat equivalence.

The independent normal-core run `build/audio-exit-long-normal-01/snes`
produces byte-identical timeline and WAV to the observed run. Instrumentation
did not perturb this measured route.
