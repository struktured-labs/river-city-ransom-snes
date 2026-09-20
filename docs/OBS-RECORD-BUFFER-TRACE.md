# Recording-buffer accounting during the physical audio mismatch

Review: <http://127.0.0.1:8766/obs-buffer-review-1785/>

The previous turn excluded observed monitor-lock drops and resampler frame-count
changes for one instrumented gameplay episode. This investigation observes the
recording source's buffer itself. No ROM changes, OBS restart, or game restart.
Rival still runs test cartridge `0e9ba29becef`, now paused farther right on the
school street with SNAC Yes and the OSD closed.

## Instrument and limitations

The exact OBS commit uses timestamp-based placement/append in
[obs-source.c](https://raw.githubusercontent.com/obsproject/obs-studio/d97e5ad82/libobs/obs-source.c)
and consumption in
[obs-audio.c](https://raw.githubusercontent.com/obsproject/obs-studio/d97e5ad82/libobs/obs-audio.c).
We observed the installed, hash-verified machine code, not just these sources:

- Producer endpoints: `obs_source_output_audio+0x479` and `+0x725`.
- Mixer endpoints: `audio_callback+0xa32` and `+0xa0b`.
- Both endpoints hold the actual source `audio_buf_mutex`. The trace records
  first-channel buffer byte count and timestamp, producer input-frame count,
  and mixer timestamp interval. It selects only sources submitted by DeckLink.
- Same-source transactions are checked for overlap, missing endpoints and
  unobserved size/timestamp changes between transactions. Cross-CPU trace
  delivery is sorted by captured monotonic clock. Censoring is explicit.

This is **metadata**, not PCM. It cannot rule out equal-length waveform edits,
faults later in the mixer/encoder, or faults downstream in the monitor path.
Uprobes perturb host scheduling; observer neutrality is not established.

## Results

Paused observation `1764`, audit `1765`: 2,399 producer transactions and 1,874
mixer transactions. Producer sizes were 800 frames 2,397 times and 801 frames
twice, each matching the measured input-frame count. Every mixer read consumed
1,024 frames. No unobserved between-transaction change or censored transaction.

Gameplay observation `1772`, audit `1776`: **2,398 writes and 1,873 reads**.
Producer sizes were 800 frames 2,395 times and 801 frames three times, each
matching its measured input. Every read consumed 1,024 frames. Again, no
non-append write, partial read, unexplained buffer mutation or censoring.
The trace brackets the local coordinator's ready/input-complete interval;
this is not a per-sample clock join.

The concurrent raw/AAC recording still fails fixed-offset correspondence:

- Offset trained on seconds 4–7: 270086 samples, correlation 0.998355.
- Held-out seconds 8/10/12/17/19: 0.998737 / 0.962329 / 0.973959 / 0.757172 /
  0.571468. All original scores retained.
- Diagnostic deltas: zero through second 9, -1 in seconds 10–15, -33 in
  seconds 16–22. Thus another 32-sample step occurred without a corresponding
  anomalous size change in the observed recording buffer. No PCM was retimed.
- Both actual-audio sensitivity controls pass on this episode. Prior failures
  remain failures in their original reports.
- Five interior raw silence runs remain: 33.458, 75.792, 138.125, 27.729 and
  54.354 ms. These are **not** verified dropouts/pops: no physical APU command
  trace was collected for this encounter.

The camera matcher retains 45 rejected pairs out of 1,791, with only six
accepted nonzero displacements. This encounter is weak speed evidence; no
original-speed or improved-scrolling claim. Full video and rejected pairs are
published, not replaced by an easier passing subset.

## Retained evidence

- `tools/{obs_record_buffer.bt,capture_obs_record_buffer.py,audit_obs_record_buffer.py}`.
- `build/obs-record-game-buffer-1772/`, `build/obs-record-game-buffer-audit-1776/`.
- Coordinated capture/input: `build/obs-record-buffer-game-1773/`.
- Raw recorder: `/home/struktured/Videos/drmario_sessions/rcr-obs-buffer-game-1773/`.
- Original video: `20260918_174315_struktured_v6c_part2.mkv` in the parent.
- Audio/camera/branch reports: `buffer-probe-audio-1780`, `buffer-probe-camera-1784`,
  `buffer-probe-branch-1783` under `build/`.
- Handoff screenshots `1778` (SNAC Yes) and `1782` (paused, OSD closed).
- Review `1785` preserves encoded video/audio exactly; all 21 served artifacts
  and five native raw gap excerpts verified by hashes/sample equality.
- Full suite **954 tests pass**, including eight new transaction-parser tests
  exercising extra samples, missing records, partial traces and buffer changes.

Recording stopped, raw debug tap removed, original adapter properties/links
and OBS audio settings restored. Saved SNES.CFG unchanged; old ROMs retained.

Next useful evidence is PCM at the common DeckLink/OBS input versus each
downstream branch, or monitor delivery accounting after its queue. The observed
buffer mechanism is excluded only for this instrumented run; do not keep
repeating the same metadata probe hoping it will certify waveform fidelity.
Actual SNES sound quality, rare slowdown and full-game scrolling remain open.
