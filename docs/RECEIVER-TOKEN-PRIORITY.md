# Pending-token receiver4007: local gain, source divergence unresolved

No promotion, default change, hardware/OBS action or EverDrive deployment.
Graphics baseline3955 remains unchanged. Candidate4007:
`839b76b4767a6e74dee1166d1c3bbf9e8298fb64bc00f8007033524a434cd0cc`.

## Fresh evidence and change

CPU4003/4004 replays are fully neutral to their respective3955/3996 controls,
including all9,090 primary frames and native PCM. Replay23.878/24.408s.
At8532 the original sound driver takes34316 master clocks in both cartridges.
In3996 the sender grows22224→28454, including a final-byte wait772→7926.
The previous frame's boundary service also moves earlier37→33, while8532
still enters through the ordinary line80 interrupt. Shortening one wait does
not guarantee a better inter-packet interval.

SPC control4005 matches the old-core3996 capture; observer4006 separately
matches the exact same core. Replay22.145/23.609s; totals27.046/28.501s including
post-capture verification. The final token is already present at145545998,
PC3530, before the timer read. A pending half-frame sweep update runs before
the receiver checks again: acknowledgement takes379 SPC clocks. The preceding
packet's final token takes35. Raw instruction rows remain in4013.

4007 replaces the16 bytes3530–353F (including two verified padding bytes).
It compares the token before consuming timer0; a mismatch still polls and
advances timers, and packet completion still services the active-control timer.
No upload-size, sound-sample, graphics or CPU scheduling code change. All code
outside that block and cartridge checksum is byte-preserved relative3996.
Both command-priority and receiver changes remain experimental.

Actual-interpreter4008 passes all16 parent/trial cases: both frame modes,
four sender delays,101 packets followed by one second idle. Timer-drop and
legacy-volume-writer mutants fail.0.239s. Two new unit tests check the emitted
branch destinations and observation censoring; these do not replace execution.

## Measured result and tradeoffs

Fresh normal4009 and audio4010 complete9,090 frames with exact same-core
observer neutrality. CPU4012 is also neutral, replay25.110s. At8532 final-byte
wait7926→996 and total sender28454→24296 master clocks. Other neighboring
senders get slower:8530 21392→24560,8531 23240→26170,8533 20468→24138.

| Full stable packet gaps |3955|3996|4007|
|---|---:|---:|---:|
| Minimum ms |12.147901|12.049391|12.207397|
| Maximum ms |20.857717|21.037180|20.806999|
| Median ms |16.6374|16.642283|16.633505|

All arms retain7342 stable and1298 excluded intervals,8641 packets and
4,846,034 stereo samples.4007's worst gap is now6279→6280;8531→8532 becomes
20.762133ms. Peak6787/max adjacent step5154 versus3955 6336/4556; no clipping.
These waveform statistics do not prove audible popping or pop-free sound.
Audio analysis4011 took27.844s. The full replay pipeline's individual normal
and audio capture durations were not separately recorded; do not invent them.

All four room populations retain two-frame original game iterations, but one
room1 interval now has a busy context. Compared3955:33 changed pictures,
8269 sampled game-RAM differences, one camera sample and one game-NMI counter
sample (frame3322,1→0). Requested/delivered inputs, outer NMI counter and faults
are unchanged. Compared3996:37 pictures change. All are retained, not waived.

## Sound event fidelity blocks promotion

Measured pulse restarts drop1588→1585. Source audit4014 independently compares
198743 sent/received bytes per arm: zero mismatches, zero unflushed CPU writes;
corrupt-received-byte mutation is rejected. The CPU request stream already has
1596→1593 pulse restart bits. This rules out lost receive bytes, not a timing
regression in original sound processing.

2551 packets differ from3955, including489 with changed pulse restart flags.
The first is packet2876/frame3276: baseline performs three APU writes and
noise volume becomes33; trial performs zero writes and retains34. Do not
promote from a small packet-gap improvement while this divergence is unexplained.
Next trace the first changed CPU sound update at3276 and its scheduling context,
before broad graphics/combat qualification or another transport optimization.

- [CPU/SPC attribution and every changed picture](http://127.0.0.1:8766/receiver-token-priority-review-4013/)
- [Source/receive divergence audit](http://127.0.0.1:8766/receiver-token-priority-source-review-4014/)
- [Native audio and every interval](http://127.0.0.1:8766/receiver-token-priority-audio-review-4011/)
- [Audio issue6](https://github.com/struktured-labs/river-city-ransom-snes/issues/6)
