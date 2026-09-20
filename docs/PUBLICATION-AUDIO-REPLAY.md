# Audio comparison using recorded packet-delivery frames

This follows [the full-route stimulus replay](FULL-ROUTE-AUDIO-STIMULUS.md).
The game stays at candidate 451; no sound-engine patch or hardware restart.

`replay_nes_apu_stimulus.py --timing publication-frame` now groups each ordered
CPU APU write with the actual subsequent complete 23-byte SPC packet. It
rejects missing/reordered packet bytes, interleaved CPU writes, backward
frames, unfinished packets and unpublished writes. Repeated same-value writes
are preserved. A bound `publication-map.json` records each original trace-row
number, CPU host frame, publication frame and packet number. No audio search
or fitted alignment is used. Default `cpu-frame` mode remains unchanged.

Fresh full runs:

- `chr-pair-published-stimulus-492`: 39,454 writes, 9,408 frames, five bank
  crossings; **10,622 writes** move to a later recorded publication frame.
- `chr-pair-cpu-stimulus-493`: identical full ordered writes with the original
  CPU-frame grouping. Its stimulus/PCM are unchanged from the earlier run.
- Both reject the physical-silence, empty-frame and bank-switch control ROMs.
  Every frame checks count/register shadow and bank/pointer state.

The complete output streams were re-encoded from the original bus CSV and
compared exactly to both stimulus files. The mapping was recomputed exactly;
all write registers, values, ordering, original beam and NMI metadata remain
unchanged. All source/artifact hashes were checked after execution.

## Two preselected running transitions

Reports `chr-pair-cpu-run-495` and `chr-pair-published-run-494` select the same
source frames 7603–7674 and unchanged SNES PCM. Per-frame measurements at
the two previously identified frames are:

| Source frame | CPU-frame NES peak / RMS | Publication-frame NES peak / RMS | SNES peak / RMS |
| --- | ---: | ---: | ---: |
| 7629 | 7753 / 3332.10 | 127 / 85.40 | 0 / 0 |
| 7669 | 6511 / 2742.07 | 317 / 135.19 | 0 / 0 |

RMS falls by factors of **39.02 and 20.28** solely by respecting the recorded
packet boundary. The substantial next note now occurs in frames 7630/7670,
as it does in the SNES recording. This supports the prior diagnosis: the
large apparent extra NES signal in these two silent SNES frames was strongly
dependent on the probe's frame grouping, not proof of a dropped SNES note.
Residual differences are still measured, not declared inaudible.

`chr-pair-published-pause-494` covers all 120 paused frames. Exactly-zero
counts remain NES 56, SNES 86; differing decaying tails remain relevant.
Neither recording clips. This does not certify synthesis fidelity: the
probe still batches writes at VBlank, retimes intra-frame writes, and uses
a different native sample rate/filter/output level. Publication grouping
also deliberately models the port's delivery schedule, not original NES
game CPU timing. It cannot certify original music tempo or transport latency.

479 Python tests pass. The new boundary tests preserve early-mute/late-note
separation and repeated writes, and reject malformed publication streams.
Next audio work should target independently demonstrated channel/envelope or
physical-audio faults, not suppress legitimate notes to fit these windows.
