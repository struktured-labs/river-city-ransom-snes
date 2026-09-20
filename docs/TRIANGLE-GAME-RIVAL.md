# Triangle attack/release: Rival test build 071c89e

September 18, 2026. Experimental test handoff, not a release or pop-free verdict.

The triangle anti-click prototype is now integrated into the game. Rival loaded
`RCR-SNES-071c89e.mgl` at 09:54:51 UTC. ROM SHA-256:
`071c89e9dde88bcc5622ef6379522149e72415b51b3418a8f281f5a66774733f`.
The previous `840de24` ROM and launcher remain available for rollback.

## Change and guards

`experimental_triangle_release` is default-off and requires paired fast/reset
audio; incompatible transports fail before build input access. The SPC triangle
voice uses a short DSP GAIN attack/release instead of an instantaneous cutoff.
The helper occupies verified unused padding after the looping triangle BRR
sample. Sample data, directory initialization, and receiver bytes are guarded.
The uploaded engine remains exactly 11,391 bytes: appending the helper in an
earlier candidate changed boot timing, so that candidate was not deployed.

Only 53 bytes differ from branded parent 799: embedded SPC code and four ROM
checksum bytes. Game code, graphics, controller setup, and splash are unchanged.
This is approximate triangle emulation, not exact NES DAC behavior. The oscillator
freezes at mute, steady amplitude differs by about 0.74%, and alternate PCM mixing
is unqualified. Controller presets remain disabled; this does not improve the
requested splash bass drop.

## Automated evidence

All **666 unit tests pass**. Source-bound reports and raw captures are retained:

| Check | Result / scope |
| --- | --- |
| Actual SPC transport, report 893 | 8,481 packets match received bytes; processing 187–1,224 SPC ticks |
| Stable park NMI, report 893 | 1,555 intervals; zero late gaps; four old failures still detected |
| Main-loop trace, report 897 | 769 complete iterations, all two ticks; 768 starts, all two frames apart |
| Render holds, report 899 | Zero short 1/3/4-frame equal-two-pixel endpoint hitches in either direction; long holds retained |
| Held-voice silence, report 897 | 4,645 frames, no guarded active-voice gaps ≥10 ms; four injected failures caught |
| Same-command audio, report 898 | Frames 1250–1500; all 255 guarded packets identical; every on/off event retained |

For the 70 matched triangle boundaries, 69 have smaller adjacent-sample steps;
one worsens from 134 to 137. Maximum triangle event step falls 2,266 → 197.
The **full mix** improves at 58 boundaries and worsens at 12; its maximum event
step falls 2,256 → 1,120. Audio is not normalized, phase-fitted, or time-stretched.
This is not an all-event improvement or a perceptual certification.

Final normal capture 891 completes in 8,934 frames versus parent 800's 9,403.
Encounters diverge around park entry; the shorter run **is not a speedup claim**.
Initial input phases match, but small early stack/video differences remain.
SPC, renderer, and loop observer captures match the final normal timeline/PCM.
Triangle-isolated captures preserve each build's non-audio timeline.

## Physical capture

OBS recording/replay were stopped before testing. Two owned bounded 30-second
recordings were started and stopped; scene, mute, gain, and monitoring settings
were unchanged. The first contains the reboot and only part of boot; the second
is the **1P menu**, not combat. Recording and replay are stopped again.

`triangle-game-menu-905.mp4` is a stream-copy remux. The matching decoded stereo
48 kHz PCM is unchanged in gain. Report 906 measures 29.867 seconds, RMS 393.65,
peak 1,617, maximum adjacent step 408, and zero clipped samples. Every one-second
window has sound. All exact-zero spans are retained; the longest is 104.90 ms.
These are not automatically classified as intended rests or dropouts.
Injected clipping, a full-scale step, and 50 ms silence are detected.

Runtime SNAC is visibly **Yes** in screenshot 915; it needed no toggle. Screenshot
918 confirms OSD closed and 1P selected. The saved SNES configuration hash stayed
`066fa49a5cb02a5e73a6caa73ea937cd2711f6b78e4cdb2099a673e9229dd933`.
This is a settings check, not a physical controller-button test.

## Still open

New-build physical gameplay/paused audio, broader sound modes and rooms,
full-game equal-work speed, input latency, and the existing strict background
publication gate remain open. The old physical park holds are not waived by
these emulator results. No physical SNAC-button consumption claim is made.

Local review: <http://127.0.0.1:8766/triangle-game-rival-review-916/>.
Same-command A/B: <http://127.0.0.1:8766/triangle-game-window-898/>.
