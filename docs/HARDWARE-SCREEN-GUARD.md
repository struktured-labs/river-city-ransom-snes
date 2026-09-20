# Failed audio run retained; controller precondition hardened

Review: <http://127.0.0.1:8766/screen-guard-review-1866/>

This turn fixes a hardware-test failure, **not the remaining game audio pops**.
The attempted simultaneous command-log/incoming-PCM capture is invalid and must
not support any gameplay, speed, or audio-quality verdict.

## What happened

The temporary sound logger `985f22e5e524` was loaded on Rival. Its previous SRAM
was backed up to `build/command-pcm-save-backup-1819.srm`; an explicit paused
export produced `build/command-pcm-before-1845.srm` with 6,230 total records.
The logger has known overhead and uses the older eight-clock pitch engine;
it was never a release-speed candidate.

Saving backup RAM automatically closed the MiSTer OSD. An unnecessary F12
press then reopened it. The old replay coordinator checked recorder readiness,
but not the displayed screen. Its controller sequence consequently navigated
the OSD and restarted the diagnostic instead of traversing the street.
The original `command-pcm-game-1848` recording remains: second 0 shows the OSD,
second 8 the splash, and second 22 the 1P menu. Successful input delivery is
not evidence that the intended game scenario ran.

Direct PCM capture `command-pcm-native-1847` also contains a 5,000-frame input
packet beyond the probe's 1,024-frame bound. The decoder refused it. No packets
were discarded or concatenated into a falsely continuous audio reference.
There is no qualified decoded PCM/command comparison for this episode.

## New guard

`tools/capture_guarded_mister_scroll.py` wraps the existing recorder and replay
without modifying historical hash-bound tools. It checks a manually audited,
OSD-closed paused-street reference twice: before starting the recorder and
immediately before the single controller sequence, after recorder readiness.
A failed second check leaves the recorder's bounded cleanup path intact.

Comparison requires native **3840×2160** screenshots, using a fixed game/HUD/
pause-menu rectangle; no resizing or alignment search. Changed pixels over a
40-level channel difference must occupy at most 0.5%, with RMS at most 10.
Scene, recording/replay state, unmuted capture audio, reference hash stability,
and observation duration are checked too. Wrong geometry leaves a structured
rejection receipt. The initial geometry attempt `1855` failed before that fix
and is retained, not counted as a qualified guard test.

This is a conservative image precondition, not a universal pause recognizer.
An audited reference is mandatory; changes after the last observation remain
possible. No claim of completed positive live gameplay qualification yet.

Evidence `screen-guard-live-reject-1857` rejects the actual live 1P menu:
73.15% changed pixels, RMS 111.72, zero controller input. Offline native-image
controls accept the reference itself and reject the recorded OSD. Eight new
unit tests cover geometry, missing labels, OSD-sized changes, outside-chat
exclusion, rejection receipts, one-call enforcement and hook restoration.
All 985 tests pass. The web review has 12 hash-verified served artifacts and
14 bound source files; every original image is copied without alteration.

## Handoff and next experiment

Regular cartridge `0e9ba29becef` restored using receipt
`command-pcm-restore-1854.json`. SNAC verified **Yes** in `guard-snac-verified-1863`;
OSD closed and 1P menu visible in `guard-handoff-1865`. OBS recording/replay off,
Blackmagic unmuted, saved SNES configuration hash unchanged. No new ROM fix.

Next: repeat the simultaneous command/PCM experiment with an audited paused
reference and the guarded wrapper. Screenshot after every backup-RAM export;
do not assume that export leaves the OSD open. Reject oversized PCM packets
and invalid gameplay rather than weakening the capture checks.
