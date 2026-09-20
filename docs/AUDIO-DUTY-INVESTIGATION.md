# Pulse duty-change investigation

## RCR trace check: not established as the recurring sputter cause

`tools/analyze_duty_changes.py` validates the bus packets against CPU writes,
then classifies duty changes separately from note-reset flags and envelope
controls. `build/duty-menu-trace-01.json` contains only two duty changes, the
initial pulse setup at frame 212, across 1906 packets. Both coincide with
note resets. `build/duty-game-trace-01.json` has 36 duty changes across 1864
packets; all 26 enabled, nonzero constant-volume changes coincide with note
resets. Neither capture has an enabled constant-volume duty-only event.

This argues against the isolated duty-only restart being the cause of the
recurring menu symptom. It does not rule out note-on clicks, omitted tail
writes (3/8 respectively), other scenes or physical capture problems. The
experimental suppression remains excluded from production. Four classifier
unit tests cover duty-only events, simultaneous reset, envelope ambiguity
and malformed packets.

## Isolated experiment now captured

`tools/check_audio.py --duty` alternates pulse duty every 32 driver frames
without periodic timer/reset writes. It retains explicit mute/restart/pitch
phases and verifies control, period and enable telemetry on every frame.
`--suppress-duty-keyon` changes only the six key-on instruction bytes at
engine offsets `$BF..$C4` into SPC NOPs after verifying the unique 12-byte
preimage. This experimental substitution costs two extra SPC cycles per
duty change; it is not part of `prepare_audio.py` or any production build.

Both variants pass existing tone/pitch/activity gates in
`build/duty-only-01/{current,suppressed}`. The explicit waveform audit at
`build/duty-only-01/site/index.html` measures 600 samples following driver
frames 32/64/96/192/224/256/288/320, with no waveform phase alignment.
Every current-engine event has a five-sample near-zero run (about 0.156 ms).
The suppressed variant has at most one near-zero sample in these windows.
Both channels are measured, with left-channel waveforms and complete stereo
WAVs on the page. Hashes bind source reports, WAVs and timelines.

This establishes a repeatable duty-key-on gap, not a perceptual click verdict
or equivalence to original NES output. A NES duty-only reference and a trace
of real RCR duty changes are still required before adopting the experiment.
The generic sustained-tone gates alone pass both variants and do not measure
phase continuity. No hardware deployment.

The existing isolated retrigger probe still passes in
`build/audio-popping-retrigger-01`. It measures sustained pitch, stereo
activity, clipping and near-zero intervals; it does not certify every
register transition or the reported game clicks.

## Source and binary evidence

Memblers' [original source archive](https://membler-industries.com/SNES/2a03-src.zip)
was retrieved from the location he identifies in his
[source announcement](https://forums.nesdev.org/viewtopic.php?t=6913).
Archive SHA-256:
`5a524d0e608721f705a0c625af6ceb054d0861e0a2508bdd52168773920c7d6d`.
Its `spc.asm` SHA-256:
`87138f1d73fe83bf6966c0c2db0c71daf154d062eddb2b496f12f065476ce1d4`.
Local archive: `/tmp/rcr-2a03-source.zip`. No source archive code was executed.

The original `sq1_sample_change` / `sq2_sample_change` paths change the DSP
sample index and issue a key-on when the pulse duty sample changes. These
instruction sequences occur exactly once each in the pinned binary used by
this port:

- Offset `$00B9`: `8F04F2 FA64F3 8F4CF2 8F01F3`.
- Offset `$019B`: `8F14F2 FA65F3 8F4CF2 8F02F3`.

This binds the specific source behavior to the current binary without
claiming the entire downloaded source assembles byte-identically.

The local Rumbleminze template at commit
`64958b6bb21d348d18e40f60e7bb110faae98d3f`
([SPC source](https://github.com/rumbleminze/nes-to-snes-template/blob/64958b6bb21d348d18e40f60e7bb110faae98d3f/src/spc/spc.asm))
no longer keys on in the first pulse's duty-sample-change block, but still
does in the second. It separately handles note-start resets. This asymmetry
is a useful comparison, not evidence that copying either path fixes RCR.

The pinned FCEUmm `Write_PSG` paths for `$4000/$4004` update duty/volume
registers without resetting the pulse sequence as a high-timer-register write
does. A DSP key-on at a duty-only change is therefore a candidate mismatch.

## Next falsifiable test

Hold timer, volume and channel enable fixed while alternating duty only.
Record the exact register schedule and audio, then compare the current SPC
with a disposable, preimage-checked duty-key-on mutant. Do not remove genuine
note-start behavior. Verify pitch, sample continuity and duty response, and
compare against original NES behavior before adopting a production patch.
The audible click hypothesis remains unproven; no audio patch or hardware
deployment was made during this investigation.
