# Paired gameplay audio: actual elapsed delivery gaps

`build/paired-game-audio-gaps-02/index.html` binds the complete observed
paired-game capture, ordered CPU writes, acknowledged packets and unmodified
stereo WAV. It includes 23 context clips selected by actual elapsed clocks.
All 7354 completed NMIs have exactly one ordered packet; no unfinished tail.

The old raw-frame method selected 121 intervals spanning more than one
normalized frame-number boundary. Actual timestamps show only 23 intervals
longer than 536049 master clocks (1.5 nominal NTSC frames). A two-boundary
distance is not necessarily a two-frame duration. No existing benchmark
gate was relaxed: this threshold selects review clips, not passing sound.

Across all 7353 completion-to-completion intervals:

- Minimum 234830 master clocks.
- Maximum 11431860 master clocks (31.989 nominal NTSC frames).
- Mean 365107.8398 master clocks.

Long intervals occur in boot/settings/story/street loading, right_08,
enter_alley, enter_shop, observe_shop_exit and mall_right_03/04. The five
longest (one about 32 frames, four about 22) have zero RMS and zero absolute
peak in the existing conservative interior window. This does not prove
their boundaries are free from clicks, or that silence duration matches NES.
Shorter intervals and synthesis discontinuities remain relevant.

The revised ACK analyzer retains optional absolute timestamps in completion
records and reports completion-to-completion timing separately from data
transfer duration. The PCM audit supports paired ACKs and selects actual
long intervals when timestamps exist, retaining legacy frame-gap selection
only for old traces without absolute clocks. All 141 Python tests pass,
including a case where a two-frame-number gap lasts roughly one frame.

This evidence argues against treating every two-frame-number gap as an
audio stall or forcing silence across arbitrary gaps. It does not establish
the root cause of reported popping. Next audio work should compare synthesis
and update-boundary behavior in the shorter, non-loading sections as well
as independently compare transition silence to the NES reference.

Reproduce with `tools/audit_audio_gaps.py --paired --length-gate --capture
build/paired-game-observed-02/snes --ack build/paired-game-ack-02.csv --bus
build/paired-game-bus-02.csv --out FRESH_DIRECTORY`. No ROM or Rival change.
