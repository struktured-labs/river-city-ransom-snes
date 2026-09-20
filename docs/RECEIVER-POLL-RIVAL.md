# Receiver-poll build: Rival hardware trial

September 18, 2026. The combined receiver/compact-row candidate is now deployed
on Rival. This follows the emulator-only [timing investigation](RECEIVER-POLL-TIMING.md).

[Watch the hardware recording, screenshots and original audio](http://127.0.0.1:8766/receiver-poll-rival-review-1479/).

## Exact build and handoff

- Cartridge: `build/receiver-poll-index-1438/native-cpu.sfc`.
- SHA256: `339d2b220a3a921626980f1e197ef4a606e16103093824f95f5649004bf00b74`.
- Rival file: `/media/fat/games/SNES/RCR-SNES-339d2b220a3a.sfc`.
- Core: `_Console/SNES_20260603.rbf`; hash-named launcher and running process
  checked again when publishing the review. The previous cartridge remains.
- SNAC restored to **Yes**, OSD closed, game paused on the school street.
  Saved `SNES.CFG` hash is unchanged. No controller mappings were replaced.
- Only this trial's recordings were stopped; its raw audio tap was removed.
  OBS scene, mute, volume and routing settings match the pre-trial snapshot.

The exact build passed all three tested room-entry comparisons, 3,823 stable
two-tick main iterations, 7,785 complete renderer frames and 8,950 received
audio packets in fresh emulator captures. Those results are not a physical
full-game speed or audible-pop certification. Graphics, splash sound and
controller presets were not changed in this receiver/row-conversion trial.

## Physical trial and retained limitations

An owned 30-second recording contains a 22.7-second wall-clock input sequence:
unpause, right/jump traversal, left/jump traversal, then pause. Screenshots show
the game consuming input and encountering goons. Input is not synchronized to
individual game frames. The linked MP4 stream-copies the original recorded
video and first audio track; it is not a replacement emulator capture.

The camera matcher accepts 1,771 of 1,791 adjacent pairs across 1,792 frames;
all 20 rejected pairs remain in its report. It finds 30 two-frame holds between
equal nonzero camera steps and no one-, three- or four-frame holds within that
qualified subset. Other motion sizes and 10/12/18/26/46/47-frame holds remain.
This is encouraging, but does not prove original NES speed, uninterrupted
scrolling, or correctness outside this episode.

## Audio: a real gap and a separate capture-timing issue

The harness compares simultaneous pre-mute raw capture PCM against an exact
decode of the OBS AAC track. It rejects a retained silent-monitor negative and
detects a deliberately injected 100ms AAC-only cut.

One gameplay silence starts at AAC time 16.404s: 10.667ms in AAC and 17.042ms
in the corresponding raw signal. Its command-level cause remains unknown.
Initial/pause silences and an incompletely covered tail are retained, not
silently discarded. The page includes native samples surrounding the gap.

The fixed offset fitted only on seconds 4–7 is 270,508 samples. Later held-out
correlations deteriorate (approximately 0.835 at second 12, 0.605 at 17 and
0.683 at 19). These remain failed fixed-offset comparisons.

A separate diagnostic searches a bounded local lag in **every** complete
one-second window from seconds 4 through 22. The best relative lag is unchanged
through second 11 and shifts by -32 samples from second 12 onward. Seconds
13–22 then correlate above 0.998; the mixed transition window remains lower.
Identity, known 32-sample shift and silent-input controls pass.

That 0.667ms change is between recording branches. It does not identify which
branch inserted/dropped samples, establish a ROM timing defect, explain the
17ms gap, or waive the fixed-lag failure. Listening excerpts use the original
fixed offset; no audio is normalized, resampled, phase-corrected or de-gapped.

## Evidence and next work

The review binds cartridge, source reports, recorder cleanup, unchanged full
screenshots, video and native audio with SHA256 hashes. The underlying reports
are boot1449, gameplay1466, audio1473, camera1474 and branch-step1478; handoff
screenshots1475/1477 show SNAC restored and the paused game.

All 26 published artifacts were fetched over HTTP and hash-checked; both gap
excerpts equal their source PCM slices sample-for-sample. All 877 unit tests
pass, including the capture-lag controls; `git diff --check` is clean.

Physical pops, original-waveform fidelity and broader gameplay speed/scrolling
coverage remain open. Next audio work must separate capture discontinuities
from game/SPC output; a local alignment improvement is not an audio fix.
