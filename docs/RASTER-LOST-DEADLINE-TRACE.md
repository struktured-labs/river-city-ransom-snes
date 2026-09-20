# First lost raster deadline, traced

Host-only observer `tools/snes9x_raster_jobs_trace.inc` runs against exact
`build/raster-worker-01/native-cpu.sfc`. The separate core is
`/tmp/rcr-snes9x/libretro/rcr_raster_jobs_libretro.so`, pinned 7a8878f.
Capture `build/raster-jobs-01/snes` completes 2036 frames. Both its complete
timeline and WAV compare byte-for-byte equal to the unobserved experimental
baseline `build/raster-worker-baseline-01/snes`.

Evidence CSV: `build/raster-jobs-01.csv`. Reset-time pre-clear WRAM contains
garbage and must be excluded; the first gameplay arm occurs at frame 897.

| Frame | Line | PC | Action |
| --- | ---: | --- | --- |
| 897 | 20 | C7:295A | Schedule first job, targeting line 30 |
| 897 | 20 | C7:2923 | Enable NMI + vertical IRQ ($A0) |
| 897 | 21 | C7:6045 | Hardware stub writes $4200=0 |
| 897 | 21 | C1:2005 | Dispatcher also writes $4200=0 |
| 897 | 49 | C7:6071 | Restore $4200=$A0; target remains line 30 |
| 898 | 30 | C7:295A | Next arm finds the first job still pending |
| 898 | 31 | C7:2923 | Counters now scheduled=2, overwritten=1, served=0 |
| 898 | 33 | C5:29AC | Second job reaches its timer IRQ worker |

The first job's timer was disabled throughout its target scanline. This is
not just an IRQ pending-bit acknowledgement failure: no event was generated
at the target. Restoring the same expired target did not recover it.
The build manifest identifies shared stub $6045 as **STA $2001 (PPUMASK)**;
several source sites share it, so this trace alone does not identify the
original calling PC. Its dispatcher transaction spans roughly 28 lines.

Frame 899 repeats the pattern on a shorter transaction: target 43, disable
at line 42, restore at line 44, no worker for that job before the next arm.
Thus even modest hardware-access transactions can cross the deadline.

Next experiment should detect an expired target at a guarded enable boundary
and re-arm a real timer event, using the full nine-bit beam position and
frame identity. This is a late-service recovery mechanism, not proof of
meeting the original line-30 deadline. Preserve separate late and lost-job
gates; do not hide late service by merely making scheduled/served balance.
An alternative CPU-mask design must preserve shared-mailbox atomicity and
the game's coroutine/flags ABI before replacing hardware masking.

No production/default ROM changes or Rival deployment in this observation.
