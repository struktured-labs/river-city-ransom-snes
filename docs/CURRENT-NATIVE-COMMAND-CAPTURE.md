# Current-engine physical commands and native gameplay PCM

Review: <http://127.0.0.1:8766/current-native-review-2085/>

Diagnostic2025 uses the same five-clock SPC engine as regular1699. Its ROM
differs from the older seeded logger1613 by42 SPC bytes and4 checksum bytes;
CPU logging and rendering are unchanged. This is not the newer graphics
candidate1976, nor a timing-neutral release build. Fresh emulator coverage2028
matches all3,137 selected records to actual received bytes; observer-on/off
SRAM, timeline, RAM, image and PCM are identical. Wrong-byte control rejects.

## Physical evidence now survives the complete validation chain

Boot2031 and guarded episode2054 ran on Rival. Before gameplay, scoped reader2051
validated two identical complete exports (681 records). After the recorded
22.7-second input sequence, export2063 and repeated explicit export2068 both
validate at1,919 records. All681 shared records agree; all1,238 new records
survive, with zero timeout flags and1,237 consecutive one-NMI intervals.
Unlike the previous torn baseline, this episode qualifies for command replay.

Native probe2053 and decoder2059 retain2,398 complete input/common pairs,
1,918,400 stereo S16 frames at48kHz. Every common float sample equals its native
input sample divided by32768. No dropped/repaired chunks, resampling or gain
normalization. Probe and logger overhead remain unqualified.

New `audit_native_packet_episode.py` binds cartridge, logger qualification,
stable snapshots, screen guards, recording/export order, PCM and restoration.
It intentionally makes no cadence or pop-free verdict. All physical silences
of at least10ms remain in report2079, including leading pause,46.083ms and
15.354ms gameplay gaps,251.771ms near ending pause, and trailing silence.

## Same-command replay narrows two gaps, not all popping

Fixture2080 replays all1,238 exported packets with the exact embedded SPC.
Normal2081 and DSP-observed2084 produce identical PCM/timeline/RAM/image;
actual received bytes match and raw DSP PCM equals delivered replay PCM.
All243 eligible pulse restarts have correct initial pitch and no stale nonzero
onsets. This is an emulator result, not physical DSP readback.

A single onset-anchored lag of11.306s is calibrated within±40ms using replay
4–7s; training correlation0.758467. Nine held-out correlations0.694188–0.903971
remain in review2085. An unrestricted search selects a later repeated phrase
at21.356s; that alternative is retained but not applied. Native listening
clips are untouched. There is no per-gap alignment or waveform-phase fitting.

The46.083ms and15.354ms physical gaps overlap replay silence99.944% and100%.
Nearby packets contain quiet commands; replay DSP pulse/noise volumes and
triangle pitch are zero, with triangle GAIN release159. This supports commanded
rests for these two gaps, not missing transport packets. Cold SPC state,
unknown within-frame timing and imperfect correspondence prevent sample-exact
causality. Pause-edge gaps outside emitted command coverage remain unresolved.
The strongest nonzero sample step has its own unclassified native excerpt.
Intermittent pops, original-speed gameplay and release readiness remain open.

Review2085 preserves original encoded OBS video/audio streams, eight video
frames in a web collage, whole native input WAV, unchanged physical/replay
excerpts, fixed-scale waveform plots, and restoration screenshots.

## Handoff

Restore2069 reloaded regular `0e9ba29becef`, not a savestate. SNAC **Yes** was
visually verified2075; clean screenshot2083 confirms OSD closed at1P selection.
Saved SNES configuration unchanged. Owned recorder stopped, temporary monitor
tap removed, OBS audio properties and links restored. No files deleted.

Next: investigate nonzero popping using the bound native PCM; independently
qualify the newer rendering/speed candidate before a user-facing promotion.
