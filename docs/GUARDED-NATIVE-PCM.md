# Guarded gameplay capture: usable PCM, rejected command baseline

Review: <http://127.0.0.1:8766/guarded-pcm-review-1914/>

## Actual result

The screen-guarded hardware run completed in gameplay, not the MiSTer OSD.
Both fresh screen checks passed against the manually audited paused screenshot
`guarded-reference-1890.png`. The recorder and 40-second native-PCM probe
completed successfully. Native PCM brackets the controller interval.

`guarded-decoded-1895` contains **2,398 complete input/common packet pairs**,
**1,918,400 stereo frames**, S16/48 kHz incoming PCM. Every observed OBS
common-float sample is exactly input S16 divided by 32768. No packet-size
rejection, missing pairs, probe warnings, resampling or gap repair occurred.
Probe overhead remains unqualified; the diagnostic logger is not a release
or performance-neutral build.

All exact-zero intervals at least 10 ms are retained:

| Native sample interval | Duration | Position |
| --- | --- | --- |
| 0–262863 | 5.4763125 s | Leading paused silence |
| 1284382–1296459 | 251.604167 ms | Near the ending pause |
| 1302429–1918400 | 12.832729 s | Trailing silence |

There is no other ≥10 ms exact-zero interval in this capture. This is **not**
proof against nonzero clicks, pitch defects, shorter discontinuities, or the
user's intermittent sputtering. No sound fix is claimed. Video24s shows the
pause menu. The internal silence has an unchanged native-rate excerpt; its
classification as commanded rest versus fault remains open.

Original recording:
`/home/struktured/Videos/drmario_sessions/20260918_183809_struktured_v6c_part2.mkv`.
The published MP4 preserves the encoded video/first-audio streams exactly.
The separate native WAV bypasses the previously diagnosed OBS monitor branch.
Ten served artifacts, 17 source bindings and the native excerpt were verified
by HTTP hashes/source hashes/sample equality.

## Baseline export race caught, not waived

Before the run, an explicit Save Backup RAM request was followed by a file
copy. That copy (`guarded-before-1889.srm`) is **invalid**: header total 6,869,
but records 6,382–6,868 contain sequence numbers exactly one ring capacity
(4,095) older. Their markers/checksums are valid for those older records.
The first stale record starts at file offset 73,216, exactly a 512-byte
boundary. A read racing a partial file export is consistent with this pattern;
the precise write/read schedule was not traced.

Post-run and repeated paused exports both fully validate at total **8,107**
and are byte-identical. This does not retroactively validate the torn baseline.
The strict episode audit correctly refuses it. All files remain unmodified.
No qualified same-command replay, packet-to-sample attribution, or game-audio
causal conclusion is presented for this run.

Read-only helper `tools/read_mister_packet_export.py` now requires complete
ring validation and two consecutive identical valid snapshots. A minimum
record count rejects an unchanged older save; a repeated export can require
the exact previously validated digest. Every invalid/stale snapshot and its
error are retained. Bounded attempts fail closed. This helper must run **after
the save request and before any gameplay replay** on the next experiment.

Five new tests cover stale-but-valid files, torn-to-valid progression,
changing valid files, interrupted stability and exact-repeat checks. A live
readback after restoration also verified the existing diagnostic save twice
against the known post-run digest (`guarded-validated-export-1913`). That is
a readback test, not a second gameplay experiment. **990 tests pass.**

## Handoff

Rival restored to regular cartridge `0e9ba29becef` by receipt1907. SNAC verified
**Yes** in screenshot1910; OSD closed and normal 1P menu in1912. OBS recording/
replay off, Blackmagic unmuted, saved SNES configuration unchanged. The original
diagnostic save was backed up in1887 before further export; no files deleted.

Next experiment must use the validated baseline reader before the guarded
capture, not another fixed sleep. Speed/scrolling and perceptual audio gates
remain open; this turn does not change the game ROM.
