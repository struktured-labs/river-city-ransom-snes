# Split sound/preparation IRQ experiment rejected

Host-only timing observer `tools/snes9x_rearm_timing_trace.inc` measures
raw frames 6700..6900. `build/rearm-timing-02/snes` matches the full retained
experimental re-arm route timeline and WAV byte-for-byte. Its CSV records
99 camera writes, only 9 before line 32, spanning lines 23..239. The 201
combined worker entries span lines 30..83. At camera value 110, raw frame
6833 writes at line 178 while published low scroll still equals 108.

Experiment `build/raster-split-01` sends sound from the first IRQ, then arms
a second IRQ at line 128 for graphics preparation. This gives the game
thread an interval between the two services; pending job completion occurs
only after preparation. It does not change original graphics or predict
camera motion.

Results:

- Baseline 1963 frames and long route 7559: both ten frames slower than
  combined re-arm worker (1953 / 7549).
- At mall_right_07: 6202 scheduled, 6201 served, **one overwritten**,
  23916 re-arms. Accounting balances but service correctness fails.
- `build/split-timing-01/snes` full timeline/WAV match the normal split
  capture exactly. Its corresponding CSV observes 94 camera writes, only
  3 before line 32, range 23..239. These raw-frame windows are not identical
  game-time samples, so the proportions are diagnostic, not a paired causal
  benchmark. At logical camera 110, frame 6849 writes at line 108 with
  published scroll still 108: earlier than combined worker at that value,
  but still well past the display split.

Moving preparation later does not by itself restore the original camera
deadline or prevent lost work. The split was reverted. Rebuilt
`build/raster-split-revert-01/native-cpu.sfc` compares byte-for-byte equal
to `build/raster-rearm-02/native-cpu.sfc`. All 125 Python tests still pass.

Current evidence points back to main-thread adapter/critical-section cost
and the time at which scroll is published; a timer relocation alone is
insufficient. Exact main-thread costs before E2B1 now need attribution.
Default ROM and Rival remain unchanged. No audio-fidelity pass is claimed.
