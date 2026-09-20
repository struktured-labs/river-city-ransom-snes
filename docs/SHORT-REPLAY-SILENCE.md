# Short silences under the same NES/SNES commands

September 18, 2026. Offline investigation; no game patch, Rival input, restart,
or OBS mutation. Current test game remains `fa882cb61138`.

[Native-rate comparison clips and every gap](http://127.0.0.1:8766/replay-short-silence-1370/).

## What changed in the evidence

The former broad silence gate excluded short boundary cases. The new audit
retains every exact-zero interval of at least **5 ms**, including its partial
source callbacks. It uses existing candidate packet replay1329 and actual
DSP/receiver trace1333, plus a fresh neutral NES pre/post-filter observation1365.
Both complete replay payloads are independently reconstructed from the original
captured CPU bus; no matching-by-melody or fitted waveform offset is used.
The replay's embedded SPC bytes equal the deployed game engine exactly.

- 2,906 source frames and 2,512 actual received packets checked.
- All 2,330,432 NES filter outputs reconstructed with the exact integer recurrence.
- Complete NES timeline, PCM and RAM unchanged by the observer.
- 210 complete-coverage SNES silence intervals retained.
- Within each gap, at most **0.624220 ms** falls outside packet-commanded quiet
  state at actual SPC ready. This is a boundary measurement, not a waived delay.
- All 548 completely silent SNES callbacks have constant NES pre-filter input
  in the corresponding source callback. Partial callbacks remain separately
  visible, including changing NES input at their boundaries.
- Initial silence extending outside source coverage is explicitly censored.
- Two actual PCM mutations inject 10 ms of silence while measured gate/packet
  conditions remain open/active. Both detectors catch their respective injections.

This does not identify a sustained missing note in this command replay. It also
does not resolve the two gaps in the physical gameplay recording: their actual
commands are not known, and the players do not reproduce game sub-frame load.

## Important failed simplification retained

Checking only DSP voice/master/echo volume commands leaves all 210 gaps
unclassified. In the inspected first gap, triangle volume remains31 even though
its release has made output silent. An open volume register is not proof of
an audible voice. The full unfavorable volume-only measurements remain in the
report; they are not used as an expected-sound oracle.

Packet state is separate evidence: actual ready timestamps and complete23-byte
commands indicate when the enabled pulse/noise channels request zero constant
volume and triangle requests zero linear reload. Decay tails and DSP pipeline
latency are not inferred away. NES callback matching is by source frame only,
not sample- or cycle-equivalent synthesis.

## Review and reproducibility

The review retains three native NES/SNES clip pairs, selected by largest NES
filter-tail variation in a complete silent callback, first sub20ms gap, and
largest packet-unproven boundary. Clips use the same source-frame windows at
original32,040/48,000Hz and gain; no resampling, gain matching or time warping.

`tools/audit_replay_short_silence.py` binds all source reports, engine bytes and
command-stream reconstruction. Six new unit tests cover all eight voices,
echo, exact write/sample boundaries, state coalescing, source-edge censorship,
packet quiet boundaries, and a short gap adjacent to a mute command.
**842 unit tests pass.** Final report1370 supersedes intermediate1366–1369.
Attempt1364 used the uninstrumented NES core and correctly failed for missing
filter traces; successful1365 uses the existing `rcr_filter_libretro.so`.

Next: investigate cutoff/decay fidelity without confusing expected filter tails
with lost notes, and obtain command-identified physical evidence for remaining
hardware-only cases. No pop-free, analog-fidelity, full-game speed, or release
claim follows from this result.
