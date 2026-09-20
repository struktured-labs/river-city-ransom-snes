# Guarded timer re-arm: no observed lost jobs, deadlines still fail

Candidate `build/raster-rearm-02/native-cpu.sfc` is opt-in only. Runtime
enable paths and generated adapters call `raster_rearm` after existing
critical-section guards. It checks the pending job's NMI-generation tag,
latches all nine beam-counter bits, and moves an expired/near-expiry target
to current line + 4. Re-arms are counted separately at 16-bit $1CB8.
The helper preserves E=1 caller A/P/X/Y, including hidden accumulator B,
and clears decimal mode while doing arithmetic. End-to-end ABI negative
controls for this new helper remain needed; earlier isolated IRQ tests are
not a substitute.

The helper intentionally does not attempt recovery at line 240 or later or
across an NMI-generation mismatch. Such failures remain visible through
the pending/overwritten counters. It does not guess a timer deadline across
frame wrap. Old initial-arm late counter $1CAE is zero in this variant
because recovery happens after the NMI guard drops; it is **not** evidence
of on-time arms. The strict audit now also rejects any $1CB8 re-arm.

Measured results:

- Baseline: 1953 frames vs retained 1956 and first raster worker 2036.
  Final 1055 scheduled = 1055 served; zero overwritten; **4734 re-arms**.
- Long route: 7549 frames vs retained 7552 and first worker 7632.
  At mall_right_07, 6199 scheduled = 6199 served; zero overwritten or
  pending; **18648 re-arms**. These counts fit the 16-bit fields.
- `build/raster-rearm-audit-02/report.json` correctly fails deadline quality
  despite balanced job accounting. The audit exits 1.
- Baseline original-speed report `build/raster-rearm-quality-02` still fails
  settings and story transition gates. A three-frame total reduction is not
  full-speed equivalence.
- Moving-camera comparison refuses mall_right_00 before pixel comparison:
  original logical camera (5,5), candidate (3,3). Thus no same-camera pixel
  pass or scrolling fix is claimed. No reference shifts were introduced.
- All 125 Python tests pass, including new generated recovery-call branch
  layout and balanced-but-rearmed rejection tests.

The new mechanism recovers jobs lost by hardware masking, but repeated
re-arming is costly and does not achieve the original raster deadline.
Next work must reduce deadline-crossing critical sections and measure
actual worker/camera scanlines, then verify complete audio packet contents
and timing. Balanced counters alone cannot prove sound fidelity.

Default rebuild `build/raster-rearm-default-02/native-cpu.sfc` remains
SHA256 `9d72565ce36e59b77343cd9454128b07fec46e38635cded4641b4e0b8f5fca44`.
No Rival deployment.
