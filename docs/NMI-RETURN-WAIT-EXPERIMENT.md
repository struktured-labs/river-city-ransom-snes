# Rejected removal of the NMI-return VBlank wait

The ordinary translated NMI return saves/restores original registers, waits
on $4212 until VBlank ends, drops NMI depth, restores interrupt enables,
and RTIs. Hypothesis: because entry reads $4210, removing that wait could
release original main-thread work earlier without a duplicate interrupt.

Experiment removed only the `LDA $4212 / BMI` loop from the return path,
using the paired-audio/FastROM candidate and all six reference traces.
`build/nmi-no-wait-01` and its baseline/long captures preserve the experiment.
The runtime edit has been reverted.

Measured baseline 1953 frames versus paired parent 1945; long 7549 versus
7541. Both are eight frames slower. Original-speed settings/story gates
still fail. Room sequence remains 0,1,2,3, so the existing route oracle
passes, but that does not establish identical per-frame game state.

Frame-boundary NMI-counter deltas in the paired parent are 7354 intervals
with delta 1 and 186 with delta 0; the no-wait candidate has 7362 with delta
1 and 186 with delta 0. Neither capture has a boundary delta above one.
This is evidence against obvious duplicate servicing in these captures,
not proof of hardware interrupt correctness or exact sub-frame cadence.
The extra NMIs track the longer capture; they are not by themselves a cause
of the slowdown. The precise scheduling reason remains unproven.

Evidence: `build/nmi-no-wait-{baseline,long,quality,route}-01`. Do not retain
this change on the argument that an acknowledged interrupt makes the wait
redundant: observed game timing regresses. A future coordinated scheduler
must validate any removal afresh. Default and Rival are unchanged.
