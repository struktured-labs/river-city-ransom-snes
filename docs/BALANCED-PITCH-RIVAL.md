# Balanced pitch build on Rival

September 18, 2026. The [cycle-balanced publisher](BALANCED-PITCH-UPDATE.md)
has now been deployed and recorded on Rival. No game art, controls or splash
sound was changed by this patch.

[Hardware video, full screenshots and native audio](http://127.0.0.1:8766/balanced-pitch-rival-review-1538/).

## Exact cartridge and handoff

- Local: `build/balanced-pitch-1493/game/native-cpu.sfc`.
- SHA256: `777635fa6d8647911536e9ef0ca9025fc4e04a78ed11200dfc36cd29ae4e565b`.
- Rival: `/media/fat/games/SNES/RCR-SNES-777635fa6d86.sfc`.
- Launcher: `/media/fat/RCR-SNES-777635fa6d86.mgl`, core
  `_Console/SNES_20260603.rbf`. Running process28562 and remote cartridge hash
  were checked again when publishing the review.
- SNAC restored **Yes**, OSD closed, game paused on the school street with
  nearby goons. Screenshots1532/1534 document those states. Previous ROMs remain.
- Saved SNES.CFG SHA256 remains
  `066fa49a5cb02a5e73a6caa73ea937cd2711f6b78e4cdb2099a673e9229dd933`.
  No controller mapping was replaced or configuration saved.
- OBS scene, mute, volume, tracks and monitoring match the pre-trial state.
  Owned recording stopped, raw tap removed, original links/properties restored.

## Actual recording

Boot1511 stages unique hash-named files, verifies remote bytes, and launches only
after the raw recorder's ready handshake. Gameplay1526 records a bounded
22.7-second wall-clock input sequence inside a 30-second recording: unpause,
right/jump, left/jump, then pause. All injected controls are released on exit.
The input policy matches the earlier receiver trial, but different enemy
encounters mean these are **not identical-state A/B gameplay runs**.

Actual OBS file:
`/home/struktured/Videos/drmario_sessions/20260918_150320_struktured_v6c_part2.mkv`.
The review MP4 stream-copies its original video and first audio track. It is
not emulator footage or a re-encoded reconstruction.

Camera1537 examines the upper-background strip, outside the actors and pause
menu in the inspected screenshots. It decodes 1,791 frames, accepts 1,785
adjacent pairs and retains rejected pairs488/492/516/534/542. Equal-step holds:

| Hold length, frames | Count |
| --- | ---: |
| 2 | 43 |
| 12 | 1 |
| 16 | 1 |
| 18 | 2 |
| 26 | 5 |

There are no one-/three-/four-frame holds in that qualified subset. Other
movement sizes, rejected pairs and long stops remain; this is not physical
original-speed, frame-perfect input or tear-free certification. Both matcher
sensitivity controls pass.

## Audio: useful result, not a pop-free verdict

Audio1536 compares the exact OBS AAC decode with simultaneous pre-mute raw
adapter PCM. Offset268,590 samples (5.595625s) is fitted only on AAC seconds4–7.
It includes capture buffering and is not game latency. Held-out fixed-offset
correlations at seconds8/10/12/17/19 are0.999230/0.998942/0.998916/0.999142/0.999406.
The earlier recording's persistent32-sample branch shift is not reproduced at
those checked windows. No local retiming was used to obtain this agreement.

There is no >=10ms exact-zero AAC gap inside the reviewed active window, but
**raw audio still has a10.354ms silence** at raw14.755271s (fixed-offset AAC
time9.159646s). Compression can fill the edges of a short raw silence. The
raw gap is retained and has its own unchanged native audio excerpt. Initial
silence, pause-associated251.521ms raw silence and uncovered tail also remain.

The previous17ms physical gap has not been explained or proven fixed: the
encounters differ and physical APU commands are not logged. Both recordings
share DeckLink/OBS upstream handling. These measurements cannot distinguish
an intentional rest from a synthesis fault or upstream capture discontinuity.
The retained silent-monitor negative is rejected; an injected100ms AAC-only
cut is detected. These controls establish sensitivity, not audible quality.

## Harness and next work

`tools/build_mister_game_review.py` binds the running cartridge, saved config,
recorder cleanup, full screenshots, original video and native audio. Handoff
tests reject scene/audio changes and active recorders. All21 published artifacts
were fetched over HTTP and hash-checked; the gap clip equals its raw PCM slice,
and context clips are unchanged. **887 unit tests pass**; diff check is clean.

The emulator's two one-sample callback-boundary differences remain documented
as a strict comparison failure in the preceding investigation. The hardware
trial does not rewrite that failure, certify original waveform fidelity or
close the speed/scrolling/audio objective. Next useful audio evidence is a
command-correlated physical reproduction, not treating short silences alone
as proof of missing notes or inventing smoothing to hide them.
