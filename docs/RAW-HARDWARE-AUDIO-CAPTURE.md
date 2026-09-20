# Actual raw hardware audio without changing the speaker mute

September 18, 2026. Review:
<http://127.0.0.1:8766/triangle-raw-audio-review-1034/>.

Current ROM `071c89e` was not changed or restarted. Rival was exercised through
ordinary USB input for bounded recordings, then left paused by Trash Pick-Up.
SNAC is restored **Yes**, OSD closed, OBS recording and replay stopped. The
Blackmagic volume, filters, routing, monitoring setting, and OS speaker-stream
mute are unchanged. All temporary recording links and the raw debug tap are gone.

## Capture-path fault found and handled

OBS reports Blackmagic unmuted, but its separate PipeWire/Pulse monitoring
stream has `mute: true`. Those are different controls. Recording the ordinary
monitor output therefore produced an entirely silent PCM file while the OBS
AAC recording contained game audio. The live node's actual properties confirm
the mute. That file is retained as a **rejected negative**, not evidence that
the game has no sound.

The corrected recorder uses PipeWire's `debug.wav-path` parameter on precisely
the existing Blackmagic stream. The [documented raw-sample tap](https://docs.pipewire.org/page_man_pipewire-props_7.html)
and [installed version 1.4.7 implementation](https://github.com/PipeWire/pipewire/blob/1.4.7/spa/plugins/audioconvert/audioconvert.c)
place this tap before conversion/mixing for the playback split path. Observed
output is the original four-channel signed-32-bit 48kHz stream, not the
two-channel post-mute output. FL/FR contain sound; both auxiliary channels are
exactly zero. No speaker unmute or reroute is necessary.

The recorder checks the exact node and object serial, rejects an existing debug
recording or active OBS recording/replay, sets only the debug path, and clears
it in cleanup. Adapter properties, existing links and OBS audio settings are
compared before/after. All restoration checks pass for recording 1024.

`capture_mister_dual_audio.py --raw-debug` starts the input episode immediately
on the recorder-ready handshake. The previous separately launched sequence
arrived too late for its 30-second recording. Both synchronized attempts fit
their whole 22.5-second input episode inside the recording. Actual injected
input receipts remain wall-clock requests, not frame-exact game-consumption
proof; video establishes the observed movement, transitions and pause state.

## Raw versus AAC from the same episode

Qualified recording:
`/home/struktured/Videos/drmario_sessions/20260918_080115_struktured_v6c_part2.mkv`.
Raw file and cleanup receipt:
`/home/struktured/Videos/drmario_sessions/rcr-raw-game-1024/`.
Coordinator/input receipts: `build/triangle-raw-combat-1024/`.
Audit: `build/triangle-raw-audio-audit-1032/report.json`.

Only recording seconds 4–7 select the raw/AAC offset: **270,754 samples,
5.640708 seconds**, correlation 0.999760. This is an alignment between separately
buffered capture branches, **not a measurement of game audio latency**. No
normalization, amplitude fit, resampling or time stretch is used.

| AAC start | AAC exact zero | Corresponding raw zero | AAC interval zero throughout in raw? |
| --- | ---: | ---: | --- |
| 10.837333s | 142.667ms | 178.500ms | Yes |
| 15.381333s | 225.333ms | 255.208ms | Yes |
| 15.765333s | 1,070.667ms | 1,104.854ms | Yes |
| 20.977333s | 18.667ms | 25.958ms | Yes |
| 21.909333s | 220.000ms | 253.708ms | Yes |

The initial paused interval also matches. The final 7.552-second AAC paused
tail is not fully covered by the shifted raw recording and is explicitly
unqualified, not silently truncated into a pass.

The 142.667ms gap coincides with a room-transition blackout in the actual
video. It is not an AAC-only loss: the raw stream is also quiet, for longer.
This does **not** prove the intended APU command, validate every transition,
or explain the earlier three mid-combat gaps from recording 941. Both new
branches share DeckLink/OBS ingestion, so shared silence cannot separate game
intent, synthesis, or an upstream capture fault.

Held-out fixed-offset correlations at seconds 8, 10 and 12 exceed 0.999. At
seconds 17 and 19 they drop to 0.692/0.681. A secondary diagnostic search over
±50ms finds a −33-sample (0.6875ms) shift after pause/resume, recovering >0.999
correlation. That diagnostic is published but **not applied** to the gap
comparison or used as a timing-fidelity waiver.

## Tests and audit materials

**745 unit tests pass.** New tests cover exact stream identity and ambiguity,
stereo port completeness, link ownership, raw-debug property isolation,
preservation of mute, bounded/released input sequences, fixed-lag alignment,
held-out mismatches, invalid/silent inputs, common versus AAC-only gaps, and
uncovered tails.

The auditor rejects the real all-silent monitor capture from attempt 1011.
An actual in-memory 100ms AAC-only silence insertion at second 9 is detected:
the corresponding raw interval is 99.979% nonzero. Original recordings and
raw PCM are untouched. Preliminary audit 1030 used a constructed zero negative
and a weaker sensitivity check; 1032 is the corrected current audit.

Review 1034 retains the stream-copy video, nine unaltered full-frame panels
checked against independently decoded RGB from the original MKV, source hashes,
input/capture provenance, and two native-rate ten-second listening excerpts.
Raw excerpt samples are exactly original FL/FR values; the full four-channel
file remains bound. The AAC excerpt exactly matches decoded float PCM.

Next: use this working pre-mute raw capture path for the remaining physical
audio investigation, with explicit active-gameplay versus transition/pause
classification. Do not repeat the silent ordinary-monitor path or treat the
5.64-second branch offset as a ROM timing fault. Hardware command identity,
pop-free output, old combat gaps, physical scrolling and full-game endurance
remain open.
