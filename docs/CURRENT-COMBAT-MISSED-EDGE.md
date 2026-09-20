# Candidate 3800: combat reveals a missed interrupt edge

Offline candidate SHA256:
`6a01aa4269338cc90098fce914dd65c09b1f0618ea57c28e8de2549449c4d33e`.
Not fixed, promoted, or deployed in this iteration.

[Combat pictures, native audio, and all intervals](http://127.0.0.1:8766/palette-combat-review-3817/)
· [Exact instruction evidence](http://127.0.0.1:8766/palette-combat-edge-3818/report.json).

Four fresh captures in `build/palette-combat-3814` exercise both controller ports
through ordinary two-player selection and two combat policies. Each observer run
matches its exact same-core control's complete video/state/input/native PCM.
Both original held-input bytes and movement of both actors are checked.
Each replay has 4,930 frames and no reported adapter fault.

Keeping original NMI-busy frames in the room-stable cadence measurement:

- Sustained attacks: 1,751 two-frame intervals and one three-frame interval.
- Running/jumping: 1,730 two-frame intervals and two three-frame intervals.

All exclusions, strict combat-phase failures, and censored iterations remain in
the report. This is not matched-NES-workload speed evidence. Eleven existing
combat/port/busy-frame tests pass in 0.067 seconds.

## First sustained-attack failure

The original main loop starts at frame 1837, line 142. The next start is frame
1840, line 122, although its native tick advance is only two. A tick-only audit
would miss the extra displayed frame.

Fresh instruction control 3815 and observed 3816 preserve all 4,930 primary
frames and native PCM and also reproduce the original combat control. Trace
window 1837–1840 shows:

- Native NMI entries in frames 1837, 1839, and 1840; none in 1838.
- Interrupt disable at frame 1838, line 238, cycle 958 (`C17BE0`).
- First NMI re-enable at frame 1839, line 26, cycle 1140 (`C733A6`).
- The continuously masked interval is 68,378 master clocks, crossing VBlank.
- Original sound-driver returns in frames 1838 and 1840, none in 1839; the gap
  is 725,724 master clocks (approximately 33.8 ms).

This pins a missed native interrupt and a sound-service gap in the same failing
window. It does not prove that this event explains every acoustic pop or that
the original NES never slows down. The native full-episode WAVs remain available.

The initial diagnostic selected the last redundant disable write inside the
masked region and correctly failed its expected-entry assertion. The corrected
audit walks back to the last enabled state and selects the first disable after
it, rejecting an intervening re-enable. No emulated behavior or acceptance
timeline was altered to obtain the finding.

Next implementation target: preserve the fresh VBlank edge while servicing the
older retained game NMI at the camera handoff, without permitting duplicate
game ticks, recursive ownership, unsafe graphics publication, or delayed audio.
Earlier deadline/guard experiments are not assumed safe to reuse. The exact
four-frame trace now identifies where to test that change.
