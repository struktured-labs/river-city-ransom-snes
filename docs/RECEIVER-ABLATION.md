# Receiver ablation: payload fidelity restored, no promotion

3955 remains the graphics baseline. No default ROM, hardware, OBS or EverDrive
deployment. Neither4007 nor new4025 is release-qualified.

## Request identity now measured

New sparse captures4020/4021 observe X immediately after the original LDX07FF
at802C, alongside actual sound-driver entry/normal-branch/return. The relevant
NES and SNES opcode bytes are checked before capture. Both observers preserve
their complete same-core9,090-frame primary timeline and native PCM.
Replay23.349/23.604s; totals28.312/28.905s including post-capture verification.

All230 original sound request IDs match3955→4007 in the same observed order.
No alignment or omitted request. Four request frames differ (zero-based index):

| Index | ID decimal |3955 frame|4007 frame|
|---:|---:|---:|---:|
|61|51|3121|3122|
|125|2|5938|5939|
|187|31|7480|7481|
|200|31|7892|7893|

Every subframe timestamp is retained.4007's busy returns3276/3300 remain
explicit. Missing, altered and reordered request controls fail. Equal request
identity does not prove equal sound update state, onset, waveform or NES speed.

## Text tradeoff

Fresh neutral4007 state capture4022 took32.215s and retains84 frame-boundary
WRAM/VRAM snapshots. Comparison4023 against3955 fails: three original-source
frames differ5980/5987/5988; eight comparable words arrive earlier, one later.
At5989 row25/column11, sourceEB and preparedEB08 match, but4007 VRAM remains
0008 while3955 is current. Both had the same source at5987 and preparedEB08 /
ready flags2 at5988. At5989 trial alias row25 retains flag3 while mirror89 has1;
parent both have1. Trial becomes current at5990. No deadline is waived.

## Ablation4025

ROM `305652ab86bafcb54c471947a0009e60d5da9f364d9fb6ea2ab0b8f28b012af7`.
Starting from4007, restore original idle poll entry3455 and clear the13-byte
command-priority helper3523–352F. Retain data-token-first receiver3530–353F.
Relative3955, only that16-byte SPC block and checksum differ. CPU scheduling,
graphics, original sound driver, samples and upload length remain unchanged.
Manifest marks command priority reverted; inherited fields are historical.

Executed4026 passes16 parent/trial continuous-clock and volume-ownership cases,
including both frame modes/four sender delays. Timer-drop and legacy-writer
mutants reject.0.244s. Fresh normal4027 / neutral audio4028 complete9,090 frames.

All8641 ordered23-byte CPU packet payloads now match3955 exactly; corrupted and
missing payload controls fail.1588 measured pulse restarts return, with no
clipped samples. This is not PCM equality or acoustic acceptance.

| Candidate | Minimum stable gap ms | Maximum ms | Pulse restarts |
|---|---:|---:|---:|
|3955|12.147901|20.857717|1588|
|3996 command priority|12.049391|21.037180|1588|
|4007 both priorities|12.207397|20.806999|1585|
|4025 data priority only|12.119616|20.957202|1588|

All retain7342 stable /1298 excluded intervals and4,846,034 native stereo
samples.4025 peak6563, maximum adjacent step5498; these statistics alone do not
identify audible pops. All four room populations retain two-frame iterations
with no busy-classified interval. Audio analysis4029 took29.052s.

4025 matches3955 outer/game-NMI counter and input trajectories, with38 changed
pictures,8299 sampled game-RAM differences and one camera sample retained.
Fresh neutral text capture4030 took32.279s.4031 fails exactly the same text
comparison as4007: three source frames, eight early words and one lateEB tile.
Restored sound payload identity has not repaired graphics timing or improved
the route's worst audio gap. Do not promote either receiver trial.

## Next action

Stop treating a faster individual handshake as the main audio solution. These
controlled variants recover waits but do not materially tighten full-route
pacing. The larger established variation is early camera-boundary versus normal
line80 sound service, plus varying original-driver workload. Revisit scheduling
with measured interrupt-safe windows rather than another arbitrary phase or a
CPU busy wait; the earlier wait80 experiment already slowed one combat interval.
Keep the late text generation as a tradeoff check. No original busy guard was
bypassed and no skipped update was silently replayed.

- [All metrics and every changed picture](http://127.0.0.1:8766/receiver-ablation-review-4032/)
- [Every sound request ID/phase](http://127.0.0.1:8766/sound-request-review-4024/)
- [4025 native audio](http://127.0.0.1:8766/receiver-token-only-audio-review-4029/)
- [Audio issue6](https://github.com/struktured-labs/river-city-ransom-snes/issues/6)
