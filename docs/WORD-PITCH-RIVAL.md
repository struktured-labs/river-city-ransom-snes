# Five-clock candidate on Rival: capture failures retained

September 18, 2026. [Hardware video, screenshots, native audio and all failures](http://127.0.0.1:8766/word-pitch-rival-review-1739/).

## Handoff

The word-pitch candidate is running as a **test build**, not a verified pop-free
or original-speed release. Cartridge SHA256:
`0e9ba29becef5dc548a81d016d0e0311731244a3fc2cc8292db321c9dd2ac12d`.

Rival process2055 runs `_Console/SNES_20260603.rbf` with launcher
`/media/fat/RCR-SNES-0e9ba29becef.mgl`; cartridge
`/media/fat/games/SNES/RCR-SNES-0e9ba29becef.sfc` was hash-checked again after
the test. The previous `777635fa6d86` cartridge and launcher remain available.
No files were deleted or overwritten on Rival.

The game is paused on school street beside goons. Screenshot1734 shows SNAC
**Yes**;1737 shows the OSD closed and pause menu. Saved SNES.CFG remains
`066fa49a5cb02a5e73a6caa73ea937cd2711f6b78e4cdb2099a673e9229dd933`.
OBS scene, audio mute/volume/monitoring/tracks match the pre-test snapshot.
Owned recording stopped, raw tap removed, adapter properties and links restored.
No controller mapping was rewritten or configuration saved.

## Actual trial

Boot1714 loaded the unique hash-named cartridge after the raw recorder's ready
handshake. Screenshot1715 confirmed the 1P menu. SNAC was temporarily disabled
for the existing idle USB test pad, then restored after the bounded sequence.

Episode1727 requested unpause,16 seconds right/jump,4 seconds left/jump and
pause inside a30-second recording. This is the same22.7-second wall-clock input
policy used previously, not identical game-state or frame-synchronized A/B.
The actual OBS file is:
`/home/struktured/Videos/drmario_sessions/20260918_171433_struktured_v6c_part2.mkv`.
The published MP4 preserves its encoded video and first audio stream, verified
using container-independent stream hashes.

Screenshot1728 was taken **after** recording stopped, despite its historical
filename containing `during`. Its retained receipt records that fact. The
recorded video, not that filename, is the in-run evidence.

## Failed audio correspondence, not a waived pass

The unchanged fixed-offset audit fits267,763 raw samples (5.578396s) on AAC4–7s.
Training correlation is only0.818494. Held-out8/10/12/17/19-second correlations
are0.069795/0.372975/0.421170/0.292414/0.290738. This is a failed correspondence
check, unlike the previous near-0.999 captures.

A separate diagnostic retains every one-second and50ms window from4–23s,
searching within±2,048 samples of the original offset:

| AAC window | Diagnostic offset delta | Diagnostic correlation |
| --- | --- | --- |
| 4–6s | 0 | 0.999330–0.999687 |
| 6–7s, transition | −382 samples | 0.720851 |
| 7–8s | −712 samples | 0.998641 |
| 8–17s | −744 samples | 0.997087–0.999092 |
| 17–18s, transition | −744 samples | 0.844811 |
| 18–23s | −776 samples | 0.998842–0.999701 |

This identifies changing correspondence between the two capture branches,
up to16.167ms. It does not identify which branch inserted/dropped samples,
prove a game timing defect, or resolve audible pops. Every original fixed
score and all lower-correlation transition windows remain. Diagnostic offsets
are **not applied** to clips or to the original gap comparison.

The silent-monitor negative passes. The original100ms injected AAC-cut control
**fails its existing detection criterion**:15.833% of the fixed-mapped raw
window overlaps a real rest, exceeding its unchanged5% limit. This failure is
not relabeled as success. The additional diagnostic's identity, known776-sample
shift and retained-silent-window controls pass separately.

Two active-window raw exact-zero intervals remain:15.458ms at raw14.634542s
and31.729ms at raw22.090688s. AAC also has a10.667ms gap at16.545333s. Under
the failed original fixed mapping it has no raw-gap overlap; that mismatch is
not reliable evidence of an AAC-only defect. Initial/pause gaps and uncovered
tails remain too. Actual APU packets were not logged in this production-engine
episode; the commanded-rest finding from episode1673 cannot be transferred to
these gaps. No normalization, resampling, gap removal or waveform fitting is
applied to the listening evidence.

## Scrolling observations remain unresolved

Camera1735 decodes1,793 frames, accepts1,786 adjacent pairs and retains six
rejected pairs498/517/526/544/552/560. Equal-step holds include18×2frames,
6×1frame and6×3frames, plus12/25/26/27-frame stops. The two matcher sensitivity
controls pass. The short irregular holds are retained, **not a speed pass**.
OBS cadence is not the native NMI clock; no evidence here attributes the holds
to the new SPC instructions or to capture alone.

The candidate's preceding exact9,406-frame emulator state/callback comparison,
unchanged full-game DSP ordering and reduced pitch-latch errors remain valid
but separate. This hardware run does not establish perceptual improvement.

## Harness changes and next work

The review wrapper rejects stale candidate text and renders each audio control's
actual result rather than inheriting the older review's unconditional passing
sentence. It verifies original encoded video/audio, candidate qualification,
current remote identity, cleanup and source/artifact hashes. The lag diagnostic
preserves silent and unsearchable windows instead of dropping them. Tests cover
piecewise shifts, retained fixed-lag failures and failed review controls.
**933 tests pass.**

Next: instrument the capture timeline sufficiently to separate dropped/inserted
recording samples and video frames from native game behavior, then repeat a
controlled comparison. No OBS device, gain, sample-rate, buffering or encoder
setting was changed in this trial. Original-speed, rare slowdown, scrolling
and pop-free/fidelity requirements remain open.
