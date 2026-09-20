# Earlier fixed audio phase on 3890: rejected

The working candidate remains 3890. No ROM promotion, hardware deployment or
restart. This experiment is retained as a negative result, not a release fix.

## Diagnosis from the current candidate

Neutral instruction observation 3912 covers CPU frames 8530–8533 while preserving
all 9,090 primary video/input/state frames and native PCM. It took 22.628 seconds.
At 8531, the camera boundary admits sound at line 35/cycle 390; at 8532 the normal
interrupt enters the driver at 80/1060. The original driver returns at 49/1174
and 105/1276 respectively. Thus this gap includes both an entry-phase change
and variable original-driver execution. Lowering the camera admission threshold
would not help this already admitted early call.

## Isolated trial

Candidate 3913 SHA256:
`81f8ff0cfc3e3c4ab4ec45c4e5dc901da09734fe3c72990ba3b231f1c8e18a31`.
Builder `tools/build_alias_audio48.py` checks exact parent3890 and changes only
the eight timer immediates and eight matching recovery comparisons from80 to48,
plus checksum. Camera-boundary32, depth/mapper guards, graphics and sound-driver
implementation are unchanged. Two tests constrain the changed bytes/checksum,
matching timer/recovery threshold and reject every mutated guard byte.

This tests a different scheduler composition from historical failed phase40:
3890 includes the newer camera-boundary service, missed-edge recovery and ready
mirror publisher. It nevertheless fails for the same broad reason: improving
one phase collision does not establish stable full-route service.

## Actual results

Normal3914 and audio3915 complete9,090 frames with full same-core observer
neutrality. Instructions3917 are also neutral (23.229-second replay).

| Measurement | Parent3890 | Trial3913 |
| --- | --- | --- |
| Driver return gap8531→8532 | 20.201ms | 17.313ms |
| Full-route stable packet gap minimum | 12.030ms | 9.673ms |
| Full-route stable packet gap maximum | 20.921ms | 23.506ms |
| Completed packets | 8641 | 8641 |
| Restart events | 1588 | 1587 |
| Native stereo sample frames | 4846034 | 4846034 |
| Peak / largest adjacent step | 6432 / 4530 | 6763 / 4746 |
| Clipped samples | 0 | 0 |

The stable/excluded packet populations remain7342/1298; no intervals were removed.
Full-route game-counter and input trajectories remain equal, but97 logical-camera
samples and156 pictures change. Every difference is retained. Stable-room cadence
is still two frames, which cannot override the audio regression. The missing
restart relative to the parent is not declared benign or filtered out.

The new longest packet gap is2205→2206 (room0), with another23.462ms gap at
7068→7069 (room2). Do not launch broad hardware/graphics qualification or choose
another arbitrary global phase based on the one improved park interval. The
next useful mechanism is reducing or safely structuring the masked work that
delays service while preserving original sound events and graphics deadlines.

## Evidence

- [Target trace, native140–143s clips and all156 picture changes](http://127.0.0.1:8766/alias-audio48-handoff-review-3918/)
- [Full native audio and every packet interval](http://127.0.0.1:8766/alias-audio48-audio-review-3916/)
- [Working3890 audio](http://127.0.0.1:8766/publish-ready-alias-audio-review-3897/)

Review3916 analysis took38.174 seconds, separately from replay. Neither no clipping
nor the targeted timing improvement is a pop-free claim. Physical SNES remains
untested, and the full speed/scrolling/audio objective remains open.
