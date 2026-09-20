# Reuse the guarded fill engine for ordinary repeated-byte commands

Candidate `build/repeat-shared-01/native-cpu.sfc`, SHA256
`1e1774e6d9f66712c9a56edd242bbdbf19da6d326b873f63638059fb8b62c8de`.

The C861 repeated-byte loop now uses the tested rectangular fill engine
when NMI is disabled, saving/restoring the original width/height variables
and the complete return status. NMI-enabled calls retain the original loop.
The shared engine retains its own destination, stride, latch and decimal
guards. Exact original helper preimages are checked and recorded in the
build manifest; game graphics and the SPC binary are unchanged.

| Transition | Pointer parent | Shared repeat | Original NES |
| --- | ---: | ---: | ---: |
| Boot/menu | 170 | 168 | 170 |
| Settings | 59 | 58 | 53 |
| Story | 62 | 61 | 54 |
| Street | 485 | 480 | 459 |

Baseline 1976 -> 1967. Boot and street pass the existing speed tolerances;
settings/story still fail. No tolerance or input timing was changed.
Dashboard: `build/repeat-shared-quality-01/site/index.html`.

Executed adapter case 27 checks saved width/height, A/X/Y and NZCV, output
bytes, counters and final destination/PPU address for ordinary calls,
NMI-enabled fallback (with fixture NMI-depth guard), increment-32 fallback,
and zero-as-256 count. Mutations losing width restoration or restoring
flags before the final load each fail case 27. Full adapter suite and all
113 Python unit tests pass.

The 7563-frame shop-exit route passes café menu/CHR and room-3 fixed-strip
camera/scroll comparisons. Audio audit verifies exactly one correct packet
for each of 7351 completed NMIs, with no unfinished tail. Gap histogram:
1:7326, 2:1, 3:5, 4:7, 6:1, 7:4, 8:1, 22:4, 32:1. The full PCM and
every multi-frame gap remain at
`build/repeat-shared-long-audio-audit-01/index.html`.

The independent normal-core replay `repeat-shared-long-normal-01/snes`
has byte-identical timeline and WAV to the instrumented capture. These
checks do not establish full-game speed, all scrolling encounters or
perceptual audio fidelity. Random popping remains unresolved. Rival is
unchanged; no hardware deployment.
