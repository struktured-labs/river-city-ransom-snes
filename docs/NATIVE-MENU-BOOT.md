# Boot-anchored physical menu audio, complete native packets

[Review: live screenshots, unprocessed audio, and holdout plot](http://127.0.0.1:8766/native-menu-boot-review-2024/)

The current **regular** Rival cartridge was restarted twice for diagnosis;
no new candidate was installed. ROM remains
`0e9ba29becef5dc548a81d016d0e0311731244a3fc2cc8292db321c9dd2ac12d`.
No controller events, saved settings, OBS audio settings, recordings or replay
buffers were changed. The direct-input probes were temporary and completed.
This is an audio-test improvement, **not a ROM fix or pop-free claim**.

## Unanchored menu observation

Read-only state2003 showed the existing1P menu, recording/replay off, Blackmagic
unmuted, microphone/desktop muted.30-second native capture2004 and decode2005
contain1,798 complete pairs and1,438,402 stereo frames. Every S16 input sample
converts exactly to the corresponding OBS common float sample. Native peak is
3,813; strongest adjacent stereo-channel step1,435.

A free song-phase search against emulation has several similar correlation
peaks and apparent missing-energy bins. It is **not a qualified timing anchor**,
so those exploratory comparisons cannot establish a port fault. The native
audio remains unchanged; no silence was removed or filled.

Same-ROM normal menu2007 completes2,269 frames. Long no-input reference2008
executes6,000 frames; its PCM prefix is byte-identical to the complete ordinary
capture2007. The long runner's own receipt is video-only, not a substituted
full-game correctness gate. Its ROM/core/input-profile/PCM bindings and exact
normal prefix are independently checked by the new audit.

## Restart exposed the old probe's capacity limit

Boot capture2009 brackets restart2010, but the strict old decoder refuses it:
HDMI reacquisition delivered1,479-,5,000- and1,600-frame packets beyond its
1,024-frame bound. Both input and common callbacks were reported as rejected.
No decoded2011 output was created. The failed capture is retained, not repaired
or regraded by dropping those records.

New `obs_chunked_pcm.bt` reads up to8,192 frames per callback in chunks of at
most1,024 frames. Each buffer read remains at most8,192 bytes. It uses bounded
compile-time unrolling as documented by
[bpftrace0.23](https://bpftrace.org/docs/release_023/language).
`capture_obs_chunked_pcm.py` retains binary/process identity checks, a40-second
maximum, timeout cleanup, source/artifact hashes and raw probe errors.

`decode_obs_chunked_pcm.py` requires every chunk exactly once, contiguous
offsets, exact byte counts, complete input/common pairs, unchanged source and
format, monotonic observation clocks, and complete trace boundaries. Missing,
duplicated, overlapping, truncated or nonfinite data fails closed. Packet
timestamps and every sample-duration residual remain in the report: callback
completeness alone does **not** prove device sampling continuity across reset.
No gap filling, gain normalization or resampling occurs.

Initial compilation2013 failed on an explicit integer-width mismatch; it is
retained. After the cast correction, live probe2014/decode2015 captures178
pairs/142,400 frames with exact native/common conversion and no warnings.
Tests reconstruct complete1/800/1024/1025/1479/1600/5000/8192-frame packets in
both supported integer formats and reject damaged metadata/payloads.

## Complete boot test and held-out comparison

Capture2016 brackets restart2017 and completes cleanly. Decode2019 has:

- 2,390 complete packet pairs;1,917,331 native stereo frames at48kHz.
- Complete large packets of1,131,5,000 and1,600 frames, including final partial
 chunks; input/common conversion exact throughout.
- A25.89ms timestamp residual during reacquisition, explicitly retained. After
 the ident onset, residuals range approximately−2.58 to+2.09ms; these host
 timestamp observations are not an independent device-clock proof.

Audit2022 (`audit_native_menu_boot.py`) finds physical ident onset5.95s after a
two-second silent interval; the reference ident starts1.11s. Twelve glide
frequency checkpoints agree with the ROM's curve within the existing5% bound.
This anchors the song without searching arbitrary repeating musical phrases.

The existing menu-energy diagnostic uses only the first4 menu seconds to
select one lag within±40ms of that anchor and two fixed channel gains. Those
parameters are frozen for the following **22 seconds**:

| Measurement | Result |
| --- | --- |
| Fixed file offset |4.862s |
| Fixed channel gains |0.826207 /0.826191 |
| Held-out correlation |0.966089 /0.966086 |
| Held-out normalized energy RMS error |0.151762 /0.151776 |
| Missing≥80% expected active energy,10ms bins |0 on both channels |
| Injected10ms stereo /20ms left /50ms right silence |All detected |
| Injected100ms clock slip, no refitting |Detected |

All2,200 held-out bins/channel and every calibration score remain in the JSON.
Listening clips preserve exact native sample slices and rates. The comparison
does not certify waveform equivalence, smaller clicks, timbre, gameplay SFX,
or probe neutrality. No acoustic release gate was loosened. The first review
attempt2021 stopped because matplotlib was unavailable; its partial files are
retained. The completed2022 plot uses native SVG with every bin, no dependency
installation or smoothing.

## Handoff and verification

Final live screenshot2020 was inspected: normal1P menu, OSD closed. Rival
process10380 runs the same regular launcher/core. Remote ROM hash and saved
SNES.CFG hash were rechecked; configuration remains
`066fa49a5cb02a5e73a6caa73ea937cd2711f6b78e4cdb2099a673e9229dd933`.
Controller settings were not touched; no new SNAC interaction test is claimed.
OBS scene/mute/volume/monitoring/tracks match the starting observations,
recording/replay remain off. These were restarts, not save-state restores.

All18 review source bindings,5 served review artifacts, and both native PCM
excerpts were hash/sample-verified. **1,017 tests pass**, log
`/tmp/rcr-tests-2023.log`. Next use complete native capture for gameplay and
same-run sound-command attribution; a coarse menu pass cannot clear the
reported intermittent gameplay pops or remaining physical scrolling/speed.
