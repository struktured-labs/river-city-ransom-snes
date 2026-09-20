# Isolated pause-selector audio regression

September 18, 2026. Current ROM remains `071c89e9dde88bcc5622ef6379522149e72415b51b3418a8f281f5a66774733f`.
No ROM change, restart, or audio-setting change was made for this test.

Review: <http://127.0.0.1:8766/triangle-cursor-review-1051/>.

## Result

The hardware produced all eight requested cursor beeps, with no internal exact-zero
interruption of 2 ms or longer inside their 10%-peak spans. Independent pixel checks
show the expected cursor after every tap, not merely successful kernel input injection:

Belongings → Password → Level → Status → Help → Status → Level → Password → Belongings.

| Capture | Cues | 10%-peak span (ms) | Largest internal exact-zero span (ms) |
| --- | ---: | ---: | ---: |
| Original NES emulator | 4 | 68.000–68.104 | 0.042 |
| Current SNES emulator | 4 | 66.167–66.448 | 0 |
| Rival pre-mute raw PCM | 8 | 65.208–66.417 | 0.021 |
| Simultaneous OBS AAC decode | 8 | 65.208–66.438 | 0 |

These are threshold-defined spans, not total sound durations. The native recordings
retain visibly different low-amplitude tails. No gain fit, resampling, time warping,
or claim of waveform equivalence is involved. In particular, a threshold crossing
must not be treated as a command timestamp.

All 1,895 paired SPC packets in the instrumented emulator match the bytes actually
received. The entire instrumented frame/RAM/audio timeline and WAV match the normal
emulator replay. This does **not** trace physical hardware APU commands.

## Regression policy and sensitivity

`tools/capture_mister_cursor_audio.py` reuses the recorder-ready handshake and
pre-mute capture path. It injects only four Right and four Left taps, separated by
released input; no Start, confirmation, gameplay movement, or reset.

`tools/audit_cursor_audio.py` uses fixed full-scale detection threshold 0.0005 and
200 ms separation. Its coarse gates require the expected count, relative onset
residual ≤50 ms, strong span 45–100 ms, and no internal exact-zero run ≥2 ms.
Observed hardware onset residuals are within 20 ms relative to the first cue.
These gates catch gross missing/repeated/stalled sounds; they are **not** a pop detector.

Five mutations of copies of the actual raw hardware recording are all detected:
missing cue, extra cue, internal 10 ms cut, 100 ms delayed cue, and doubled-duration cue.
Original recording samples are untouched.

`tools/build_cursor_audio_review.py` checks all nine hardware panels against a
second complete RGB decode of their source frames. A checker pinned to the current
1920×1080 OBS scene verifies exactly one arrow and the expected menu sequence.
Actual-frame missing-arrow and duplicate-arrow mutations are both rejected.
The page also includes eight original emulator frames and four native-rate clips,
each checked sample-for-sample against its source.

## Evidence

- Normal SNES: `build/triangle-cursor-snes-1036/` (2,286 frames).
- Original NES: `build/triangle-cursor-nes-1037/` (1,978 frames).
- Neutral receiver observer: `build/triangle-cursor-snes-1038/` (2,286 frames),
  alongside `-bus.csv` and `-received.csv`.
- Hardware controller/recording receipts: `build/triangle-cursor-hardware-1042/`.
- Raw PCM/recorder receipt: `/home/struktured/Videos/drmario_sessions/rcr-raw-cursor-1042/`.
- Original media: `/home/struktured/Videos/drmario_sessions/20260918_081951_struktured_v6c_part2.mkv`.
- Exact AAC decode: `build/triangle-cursor-aac-1047.wav`.
- Current audit: `build/triangle-cursor-audit-1049/report.json`.
- Current review: `build/triangle-cursor-review-1051/`.
- Restored SNAC Yes: `build/triangle-cursor-snac-state-1044.png`.
- OSD closed, paused game and idle recording: `build/triangle-cursor-handoff-1046.{json,png}`.

The failed preliminary audit 1048 rejected a wrongly selected three-byte receiver
protocol; the current audit correctly requires the ROM's paired receiver. Review
1050 predates automatic cursor checks; 1051 supersedes it.

Validation: **760 unit tests pass**; `git diff --check` passes.

## Still open

This isolated sound is repeatable; it does not reproduce or clear the older combat
gaps. Full-game speed, strict same-frame publication, hardware command identity,
and pop-free gameplay remain unverified. No new ROM is offered from this result.
Splash sound and controller presets are unchanged. Rival remains paused by Trash
Pick-Up, SNAC Yes, OSD closed, with the original speaker mute and OBS audio settings.

Next audio work should target a reproducible combat action using this now-working
raw capture path, rather than extending the quiet-menu result to busy gameplay.
