# Same-run MiSTer sound-command logging

September 18, 2026. [Recording, screenshot grid, native audio and packet log](http://127.0.0.1:8766/audio-packet-hardware-review-1690/).

## Result and current handoff

The seed-dependent diagnostic now has a verified **physical SRAM workflow**:
create its unique save file, boot the hash-verified cartridge, request Save
Backup RAM while paused, and decode the exported data. Disk seed creation
alone is not the proof: the first export contains 3,205 committed records
written by the running game. The post-test export contains 4,443 records total;
1,238 are new, and all survive the ring wrap. The 2,857 shared retained records
agree with the pre-test export. A second paused export is byte-identical.

All 1,238 episode records have valid sequence, marker, checksum and header
pointer. None flags a transfer timeout. Their 1,237 adjacent native-NMI
intervals are all one tick. This is a CPU-side transfer log, **not independent
physical SPC memory readback or a wall-clock measurement**.

The regular balanced-pitch cartridge `777635fa6d86` was restored afterward.
Rival process 32744 uses `/media/fat/RCR-SNES-777635fa6d86.mgl` and the existing
`SNES_20260603.rbf`. Final screenshots1686/1688 show SNAC **Yes**, OSD closed,
and the 1P selection menu. Saved SNES.CFG and OBS audio settings are unchanged;
the owned recording stopped and its raw tap was removed. Previous cartridges
and diagnostic evidence remain. No files were deleted.

Restoration was a **restart**, not a saved-state restore. An earlier explicit
Save state request1637 produced no file in the previously empty SNES save-state
directory; no successful pause-state backup is claimed. Bluemage was inspected
read-only and left alone: it was running another NES cartridge.

## Actual recording and retained gaps

OBS recording:
`/home/struktured/Videos/drmario_sessions/20260918_162805_struktured_v6c_part2.mkv`.
Episode1673 requests the same bounded 22.7-second unpause/right-jump/left-jump/
pause policy as previous trials inside a 30-second recording. This is evdev
input with wall-clock receipts, not a frame-exact or identical-encounter A/B.
Before/after images show the game paused. Export requests bracket the complete
recording. The published MP4 retains the original encoded video and first
audio streams, checked with container-independent stream hashes.

Raw FL/FR audio still contains these exact-zero intervals in the explicitly
reviewed AAC3..22s window:

| Fixed-offset AAC time | Raw duration |
| --- | --- |
| 3.922188s | 17.625ms |
| 4.020479s | 19.8125ms |
| 19.917979s | 11.0833ms |

Each has an unchanged native-rate audio excerpt. The raw/AAC offset271,289
samples is fitted only on AAC4..7s; five held-out correlations range
0.997865..0.998917. No local retiming, normalization or gap removal is used.
Initial/pause silence, uncovered tails and AAC edge filling remain reported.
The retained muted-monitor negative and injected100ms AAC-only cut controls
are detected.

The continuous command sequence rules out a missing logged NMI number or a
flagged handshake timeout **within this diagnostic episode**. It does not
identify which command corresponds to each audio sample, prove the NMI clock
never stalled, or distinguish a commanded rest, SPC synthesis fault and shared
upstream capture discontinuity. In particular, do not claim these gaps are
fixed or intentional merely because transport records are present.

Camera1689 decodes1,791 frames, accepts1,783 adjacent scenery pairs and retains
seven rejected pairs580/608/640/672/728/1123/1241. Equal-step holds are18×2,
7×26 and1×25 frames. Other movement sizes and long holds are retained; this
is not a full-speed or tear-free certification.

## Diagnostic qualification and harness changes

The exact tested diagnostic is seeded-gated1613, SHA256
`985f22e5e524a029f99b3ae7db0092367812293eeb61432ed386ac6d8f8ecd17`.
New seeded main/raster captures1641/1642 reproduce its full8,937-frame normal
timeline and PCM. Cadence1643 passes3,586 complete two-tick loops across four
rooms; park short irregular camera holds are absent. Its previously measured
8/6/7 load/fade offsets still fail the unchanged7/7/7 gates. This temporary
hardware investigation does **not** promote the logger to a release build or
certify that its timing represents the uninstrumented cartridge.

Failed captures1639/1640 are retained: one wrapper compared relative paths
against resolved paths; the other incorrectly intercepted `CDLL(None)` used
to flush host renderer output. `run_seeded_benchmark.py` now wraps only the
explicit selected core, preserves unrelated library loads, validates exact
SRAM readback and binds one core/ROM load. Tests cover failure restoration,
null pointers, incorrect memory sizes and unsuccessful game loads. Earlier
bound tools/reports remain unchanged.

New staging uses exclusive creation and full disk readback, not overwrite.
The episode audit rejects changed shared history, mismatched re-exports,
missing/overwritten coverage and non-bracketing export requests. It retains
timeout and non-one-tick observations as failures/evidence rather than
filtering them out. The complete suite passes **917 tests**.

Pre-entry screenshot1659 captured a red frame; subsequent screenshots show
normal gameplay. That interval was not continuously recorded and remains
visible in the review instead of being presented as a successful frame.

Next: establish the packet-to-audio time relationship and replay the recorded
command stream with explicit initial-state/sub-frame limitations. The export
workflow is now established; sample-level attribution and the audio fix remain
open. There is no need to keep repeating seed-load experiments to establish
this same fact.

## Primary-source guidance

The [MiSTer SNES core source](https://github.com/MiSTer-devel/SNES_MiSTer/blob/master/SNES.sv)
describes backup-RAM load/save controls and reset during loading. The
[MiSTer file-path implementation](https://github.com/MiSTer-devel/Main_MiSTer/blob/master/file_io.cpp)
describes ROM-derived save names. These current sources guided the experiment;
they are not a claim that current master equals the deployed June03 bitstream.
The actual export/readback results above establish the tested workflow.
