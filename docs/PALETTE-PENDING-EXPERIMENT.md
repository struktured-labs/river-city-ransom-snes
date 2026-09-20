# Palette dirty-publication experiment rejected

Candidate `build/palette-pending-01` marked $1CBB after a complete palette
conversion and skipped the five CGRAM transfers until that flag was set.
Unchanged preparation did not clear an outstanding upload. The consumer
cleared it only after the transfers, behind the existing final VBlank guard.

Executed graphics tests passed. Baseline completed in 1953 frames and long
route in 7549, both **four frames slower** than publisher-scan-01 (1949 and
7545). Room-sequence and café checks passed, but no overall speed benefit
was demonstrated. No audio-fidelity claim is made for this candidate.

The experiment exposed an oracle distinction: suppressing the upload flag
still passed prepared-RAM assertions, but failed the actual rendered-pixel
oracle. `check_video.check_cache_controls` now retains an independent
consumer-side negative control: redirect background palette DMA away from
CGRAM's data port. It must fail the actual synthetic pixel comparison,
not merely a prepared-shadow assertion. Existing cache-invalidation mutants
still require executed case 7.

The dirty-publication code was reverted. Rebuilt
`build/palette-pending-revert-01/native-cpu.sfc` compares byte-for-byte equal
to publisher-scan-01, the retained default. The complete executed graphics
suite passes with the new palette-DMA negative control.
No Rival deployment.
