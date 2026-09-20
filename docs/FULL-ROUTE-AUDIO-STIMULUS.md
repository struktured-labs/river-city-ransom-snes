# Full-route NES audio stimulus replay

Follow-up: [recorded publication-frame replay](PUBLICATION-AUDIO-REPLAY.md)
tests the timing hypothesis below with the same complete write stream.

Current game candidate remains 451, SHA256
`71407e8833617f240f0f82190764c248989daa8a6bd81a4322594dd9d1497c73`.
No game ROM, audio engine, emulator core or Rival deployment changed.

## Executed coverage

`chr-pair-full-stimulus-487` executes the complete captured stream from reset:
9,408 source frames, 39,454 APU writes, 88,316 packed bytes. The asset-free NES
probe now optionally uses mapper 2, with seven 16-KiB data banks and a fixed
code bank. All five data-bank crossings execute on the pinned FCEUmm core.
After every source frame, the test checks completion order, total writes,
24-byte register shadow, bank number and stream pointer. Physical PCM must
be non-silent. Source/capture/artifact hashes are bound in its report.

The bank switch preserves both the returned byte and the caller's register
index. Its fixed-ROM selector table contains the bank number being written,
so the selector is compatible with bus conflicts; this iNES mapper-2 run
does not itself enable conflict emulation. The local FCEUmm `datalatch.c`
implementation was inspected; no emulator modifications were made.

Three actual negative ROMs are rejected:

- Redirected physical APU writes produce silence despite correct bookkeeping.
- Removed empty-frame guard fails the write/count check on frame 1.
- Removed bank switching fails the register-shadow check on frame 1965.

The unbanked control `chr-pair-nrom-stimulus-487` remains byte-for-byte
identical to replay 484 in ROM, packed stimulus, PCM, timeline and final RAM.
Its first 3,224 source-frame/write-count pairs also equal the full banked run.
Bank switching adds CPU cycles; bit-identical banked/unbanked PCM is not claimed.

## Matched-write park audio, and a timing limitation exposed

Reports `chr-pair-same-{run,pause}-489` expose unchanged native-rate PCM,
per-source-frame peaks/RMS/steps and exactly-zero frames. There is no gain
fit, time fit, thresholded silence detection or resampling. Both channels
are checked. Missing/overlapping callback sample ranges fail closed.

| Window | NES zero frames | SNES zero frames |
| --- | ---: | ---: |
| Running, 7603–7674 | 0 / 72 | 3 / 72 |
| Paused, 8113–8232 | 56 / 120 | 86 / 120 |

Those counts are **not a new dropout/fidelity verdict**. Most extra NES
sound during the paused silent regions is a small decaying tail: peaks
1–26 and 1–141 PCM units. Different output filters/levels remain relevant.

Running frames 7629 and 7669 are more conspicuous: SNES is exactly zero,
while NES peaks are 7,753 and 6,511. Surrounding unmodified clips are in
`chr-pair-run-gap-{a,b}-490`. The actual bus trace explains why a simplistic
frame comparison can mislead here:

- At frame 7629 lines 22–26, the game writes muted noise/pulse controls
  (registers 12/4/0 = 48/240/240).
- Later in that same host frame, lines 253–261, it starts the next note:
  noise period/length and control 51, triangle period/length and control 129.
  The pulse update continues into frame 7630.
- Frame 7669 similarly contains early mute writes and late next-note writes
  (noise control 53, triangle control 129).

The current NES probe batches **both early and late writes at one VBlank**.
Consequently it can advance the next note relative to the SNES callback
window. The output mismatch is real for these recordings, but this probe
does **not** establish an erroneous SNES mute or a missing packet. Do not
patch the sound engine or move the comparison window to hide it. Next useful
work is a qualified timing-aware replay or an independently observed
channel/engine-state test of these exact transitions.

The replay preserves write order, including repeated reset writes, but is
not intra-frame/cycle-equivalent and does not observe every physical APU
write independently. Large-step comparisons likewise do not certify
inaudibility. Existing transport/key-on provenance remains valid; acoustic
acceptance, whole-game speed and broader scrolling qualification remain open.

477 Python tests pass; `git diff --check` is clean. Review:
`http://127.0.0.1:8766/full-route-audio-review-491/`.
