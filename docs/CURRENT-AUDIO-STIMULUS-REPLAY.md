# Current audio: bound event traces and an executed NES stimulus replay

Update: [the full-route banked replay](FULL-ROUTE-AUDIO-STIMULUS.md) now
extends this historical prefix result through frame 9,408, with three
negative ROMs and matched park clips. Its timing limitations remain explicit.

The game ROM remains paired-read candidate 451,
`71407e8833617f240f0f82190764c248989daa8a6bd81a4322594dd9d1497c73`.
No audio-engine patch, hardware deployment or Rival restart was made. These
changes strengthen automated diagnosis; they do not certify pop-free sound
or complete the outstanding speed/scrolling/audio goal.

## Trace provenance is now contemporaneous

`benchmark_capture.py` flushes the optional host-only game-key-on and SPC
synthesis logs before hashing them into the same capture receipt as the ROM,
core, input replay, timeline and waveform. Missing/empty logs or flush failure
reject the capture. With neither observer requested, no new flush occurs.
The pinned emulator cores are unchanged.

Fresh `chr-pair-keyon-477` completes **9,408 frames**. Its complete timeline
and PCM exactly match the independent normal capture `chr-pair-normal-452`.
`chr-pair-spc-provenance-478` verifies:

- **9,055 packets**, every reset/enable/pulse-control header field checked
  against the actual complete received packet, not synthesized missing bytes.
- **999 pulse key-on events**: 948 reset-only, 51 merged reset/duty and
  **zero duty-only** events. Both pulse voices reset in 593 packets.
- No missing writes, mismatched key-ons or unfinished packet processing.
- Last-received-byte to SPC-ready durations of **161–1,201 observed SPC
  ticks**. IPL acknowledgements are kept separate from actual engine-ready
  events. These are not DSP sample latency measurements.

New tests reject changed trace bindings, wrong packet fields, missing or
duplicated ready events, reordered ticks and missing engine startup.

## Fresh digital bounds, with their limits retained

`chr-pair-transients-479` measures all **5,015,567 stereo sample frames** and
every key-on publication frame. It finds no clipping or missing audio
callbacks. Maximum adjacent-sample step is **4,537 / 32,768 = 0.13846**, below
the existing executed isolated-NES reference limit 0.17166. Inserted full-scale
spikes and missing callbacks are rejected. All 20 strongest event clips and
the full unchanged PCM are available on the report page.

That limit is a diagnostic bound, not a psychoacoustic verdict. The reference
and candidate have different sample rates, filtering and output levels.
Passing it does not prove that smaller audible artifacts are absent.

`chr-pair-{paused,running}-audio-479` exposes the full corresponding NES/SNES
input phases without time/gain fitting. All 120 pause samples on each platform
have the game's pause bit set; all 72 running samples have it clear. Their
music/encounter states can differ, so these clips alone cannot establish
synthesis equivalence. Three exactly-zero SNES running frames (7629, 7646,
7669) coincide with delivered volume-zero pulse/noise controls and zero
triangle linear-reload values. This is not by itself proof of the NES's
precise internal envelope/length state or an unexplained transport dropout.

## Same captured writes, executed on NES

To remove gameplay-state divergence from the strongest-event comparison,
`snes/nes_apu_stimulus.asm` and `tools/replay_nes_apu_stimulus.py` build an
asset-free NROM player from the actual CPU APU write stream. The current
prefix preserves **all 13,310 writes across source frames 1–3,224**, including
empty frames and repeated same-value timer resets. It starts at reset, not a
synthetic mid-song snapshot. Frame counter, cumulative write count and all
24 register-shadow bytes are checked after every completed source frame.
Actual PCM must be non-silent. DMC, DMA and controller-side effects fail
closed; no missing DMC samples are invented.

The probe executes on the pinned FCEUmm NES core, not an offline waveform
approximation. **Important limitation:** it batches each source frame's
writes at NES VBlank; it preserves order but is **not intra-frame or
cycle-equivalent** to the original SNES CPU timing. It is a diagnostic
stimulus replay, not a replacement game or full-route fidelity oracle.

`chr-pair-nes-stimulus-484` passes and rejects two actual control ROMs:

- Physical APU stores redirected to unmapped expansion I/O: RAM bookkeeping
  remains correct, but actual sound is silent and the check rejects it.
- Removed empty-frame count test: the pointer helper's flags cannot substitute
  for the count comparison; the execution checker rejects frame 1.

The first attempt 480 had an assembler binary-include path error. Runs 481/482
exposed that empty-frame flag bug in the new probe; it was fixed explicitly.
483 passed the physical-audio control; 484 additionally executes the empty
frame negative control. Earlier failures remain retained. The player does
not yet replay the entire 9,408-frame route: the 29,844-byte stimulus prefix
fits NROM; a longer capture needs banked stimulus storage or a separately
qualified replay format.

## Strongest measured event comparison

`chr-pair-same-event-audio-485` selects source frames **3092–3116**, containing
the original strongest SNES event at frame 3104. Selection was fixed from
the SNES event audit, not searched for a favorable waveform match. PCM remains
at native rates, with no gain fitting, time fitting or resampling.

| Measurement in that source-frame window | NES replay | SNES game |
| --- | ---: | ---: |
| Sample rate | 48,000 | 32,040 |
| Peak magnitude | 13,023 | 6,437 |
| Maximum sample step | 9,697 | 4,537 |
| Step / window peak | 0.7446 | 0.7048 |
| Clipped samples | 0 | 0 |

The strongest measured transition is also large on NES under the same write
sequence. This does **not** establish every reset as artifact-free, but it
does not support removing legitimate note resets merely to suppress that
peak. Timing/filtering differences remain explicit; the comparison produces
measurements and listening evidence, not a new blanket audio pass.

Review: `http://127.0.0.1:8766/audio-stimulus-review-486/`.
Next audio work should use the common stimulus to test specific timbre,
envelope, reset or timing differences and extend coverage beyond this prefix.
The first-room 22-versus-20-frame speed gap also remains open.

474 Python tests pass and `git diff --check` is clean. Both current
provenance/replay reports' source and artifact hashes were revalidated, and
all review-page audio/evidence links respond successfully.
