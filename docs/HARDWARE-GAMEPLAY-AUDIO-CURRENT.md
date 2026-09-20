# Rival combat and paused-audio evidence

2026-09-17: same deployed branded616 ROM (`34835f8`), no new cartridge or
restart. This follow-up adds a bounded hardware-input harness and actual
street-combat/scrolling footage to the earlier menu-only audio observations.

## Reproducible hardware input

`tools/run_mister_keys.py` retains wall-clock event receipts and executed
helper hashes. `mister_key_sequence.py` creates a transient keyboard for OSD;
`mister_pad_sequence.py` injects through Rival's existing USB SNES pad. The
latter requires the exact device identity, idle buttons and centered axes,
and releases all owned controls on exit. Sequences are bounded to 55 seconds,
with per-step bounds, no opposite directions, no device grab or daemon, and
no mapping/config file writes. These are request timestamps, **not frame-exact
game-consumption measurements**. Captured video checks actual game response.

Rival's runtime SNAC setting bypasses ordinary USB input for P1. For this
episode it was temporarily changed from Yes to No in the OSD, then restored
to **Yes**. `rival-snac-restored-634.png` shows that runtime restoration;
`rival-handoff-634.png` shows the OSD closed and game paused. The original
`SNES.CFG` SHA256 remained
`066fa49a5cb02a5e73a6caa73ea937cd2711f6b78e4cdb2099a673e9229dd933`.
The saved-file hash alone does not establish runtime SNAC state. No physical
SNAC button test is claimed. At handoff Alex has one health bar; the game is
paused to avoid further damage.

## Actual captured samples

Source is the ongoing Blackmage recording:
`/home/struktured/Videos/drmario_sessions/20260916_214537_struktured_v6c_part2.mkv`.
No OBS recording/replay/scene/gain/mute changes were issued. Nearby live
receipts show Blackmagic unmuted, mic/desktop muted; these are not immutable
historical routing receipts.

- `rival-combat-633.wav`: exact recording44920..44950, 30 seconds of stereo
  48kHz PCM16. RMS476.26, peak2718, largest adjacent step2475; every second
  contains audio. Right/B/Y requests visibly move/fight/scroll, then Start
  opens the pause menu.
- `rival-paused-634.wav`: exact recording44955..44975, 20 seconds, same PCM
  format. **Every sample is zero.** The pause screenshot precedes this entire
  interval; the next OSD input follows it. No paused sputtering appears in
  this sample. This is not proof of analog silence or pop-free gameplay.
- `rival-combat-635.mp4`: browser-compatible review clip. Stream-copy seeking
  included an earlier keyframe, so it is approximately33.35 seconds, not an
  exact30-second or frame-aligned companion to the WAV. Do not derive input
  latency or speed parity from its start offset.

`audit_hardware_pause_pair.py` binds the extracted media, screenshots, event
receipts and manifest by SHA256. It requires non-silent AC in both gameplay
channels and exact paused silence. Executed negative controls reject a dead
gameplay capture and a one-sample paused click. Unit tests also reject DC-only
and dead-channel controls, wrong formats and truncated durations. It explicitly
leaves pop-free gameplay, NES-speed parity and release readiness **false**.
All 530 Python tests pass. Published media endpoints return HTTP200 and all
artifact/implementation hashes in the new report were rechecked.

Review: <http://127.0.0.1:8766/rival-gameplay-636/> (video, screenshot comparison,
unmodified decoded WAVs and all receipts). Intermittent gameplay pops,
matched-encounter full-speed benchmarking, fade/latency gates and controller
presets remain open. No new bass-ident design was deployed in this episode.
