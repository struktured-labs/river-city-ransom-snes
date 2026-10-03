# Trial: Project Nested SPC engine (builds 4303 and 4304, branch `nested-audio`)

Goal: replace the Memblers 2A03 SPC700 engine copy taken from upernes (SHA-256
`4e095134…`, no established licence) with the updated version of the same
engine in Myself086's Project Nested, which is MIT-licensed.

Status: **trial**. Build 4302 is still the release candidate. 4303 (stock
Project Nested) works, but it loses the SPC fixes that this project added on
top of Memblers' engine. 4304 ports those fixes onto the Project Nested engine
and matches 4302 on the per-voice audio checks (see "Build 4304").

## Source and licence

- Upstream: <https://github.com/Myself086/Project-Nested>, `master` at
  `cc2c892be2e4f105a4780879022777b57f62052f` (v1.8.1, 2023-07-28).
- Files: `Assembly/Project/Spc700/Spc.asm`, `Spc.Memory.asm`, `Dmc.asm`,
  `Data/*.asm`. Project Nested's host side (`Sound.asm`, `IO.asm`) is used only
  as a reference.
- Licence: the only licence file, `License.md`, is the MIT licence,
  "Copyright 2020 Laurent Courville". The Spc700 files have no headers and no
  exception. The repository does not mention Memblers; see `docs/THIRD_PARTY.md`.
- Lineage check: the assembled image shares about 5.6 KB of identical code runs
  and a 4104-byte identical table block with the upernes binary. The pulse
  ("New" pl1a) and triangle samples differ.
- Project Nested's own assembler is not public. `tools/pn_spc_asm.py` (with
  `tools/spc700_opcodes.py`) is an independent assembler for the subset these
  files use. Output: 12219 bytes at `$0400–$33BB`, SHA-256
  `34c7a2c0ed18f7c17d9848d76388a3980ece08a3419df67616742afcef23ddca`, pinned
  in `tools/dependencies.json` together with each source file's hash.
  `tools/bootstrap.py` fetches the pinned revision into `.deps/project-nested`.

## Host protocol: current engine vs Project Nested

The same in both:

- Standard IPL upload to `$0400` and jump there. The SPC sends ready token
  `$7D` on port 0; the CPU starts a frame with `$D7`.
- Register pairs: index on port 0, data on ports 1 and 2, the SPC echoes the
  index. `$F5` on port 0 resets to the IPL.
- `$4016` flag byte: `$01–$08` per-channel restart, `$10` DMC, `$20` stereo
  (RCR leaves it clear: mono), `$40`/`$80` reload pulse 1/2 sweep.
- The triangle linear counter runs on the SPC.

Differences:

| | 4302 (Memblers/upernes + RCR extensions) | Project Nested | 4303 handling |
|---|---|---|---|
| `$4015`/`$4016` | pair indexes `$14`/`$16` (12 handshakes) | ports 1/2 together with `$D7`; pairs `$00–$12` only (10 handshakes) | new sender (below) |
| Host feed | CPU loop | HDMA, four quarter-frame tables | CPU loop kept |
| Ack order in `xfer` | n/a (own receiver) | acks on port 0 before reading port 2 (fine for HDMA, racy for a CPU sender) | engine patch 2 |
| Sweep reload flag | set on `$4002/3`, `$4006/7` writes (`direct_apu_flags`) | set on `$4001`/`$4005` writes | RCR flags kept; same SPC meaning |
| Length counters | not needed (RCR always uses halt, `LENGTH-EXPIRY-SCOPE.md`) | CPU-side emulation | not used |
| DMC | none | second upload: static-range flags at `$BFFF` + 16 KB PRG | engine patch 1 |
| Port 3 | timed-receiver deadline byte | ignored | harmless |
| SPC extensions | live sweep driver, triangle attack/release, noise clock table, timed/staged receiver, restart volume, startup pitch, fast reset/duty | none of these | **not carried over** |
| Duty change | KON on SRCN change | same | — |

## Build 4303

`python3 -m tools.build_nested_audio` builds `build/nested-audio-4303` from
`build/gamer-stam-cap-4302` (SHA-256 `3d8b6112…`). Only the audio changes:

- Engine at ROM `0x120000`: the old 13110-byte image is filled with `FF`, then
  the patched Project Nested image goes in. The upload length operand is at
  `0xD2A3`.
- Engine patch 1: `mov a,!$BFFF` → `mov a,#0` (`e5ffbf` → `e80000`). There is no
  DMC upload, so the static range flags are zero instead of uninitialised ARAM.
- Engine patch 2 (`xfer`, `$04AB`): `e4f5 d8f4 d440 e4f6 d441` →
  `e4f5 d440 e4f6 d8f4 d441`. The SPC acks only after reading both data ports.
  Same bytes, same cycles.
- Sender at `$D2BC` (same entry; only caller is the `jsr` at ROM `0x81DE`):
  `$7D` wait, `$0A15` → `$2141`, `$0A16` → `$2142`, `$D7`, then pairs
  `$00–$12`. On exit C = timeout and Y = `$17`, as before; RTS is now at `$D2FE`.
- ROM SHA-256 `59fe22139385728b0e52a196274f59f62e5bf420e3e77fcecd564e909a222a3e`;
  patched SPC image `cdd49e6f94f484cfdcd5fd1f3396ff26ff746f89061dc6beca1c1dc83fb8234e`.

The smaller upload makes boot one frame shorter (street reached at frame 1169
instead of 1170). Scripted runs therefore play out differently from 4302 after
the first input; see the test notes.

## Results (2026-10-02)

| Check | 4302 baseline | 4303 |
|---|---|---|
| SPC link (`tools/mesen/spclink.lua`, 6400 frames) | pass; sender usually 19–23 scanlines | pass: 0 `$EE` timeouts, 5363/5400 frames with a call, 6007/6007 returns; usually 7–8 scanlines, worst 20 |
| Timing, Mesen (default / Gamer) | max vblank line 257 / 258, 0 batches ending in active display | 258 / 258, 0 ending in active display |
| Freeze batch, snes9x (66 runs) | 0 hangs | 0 hangs |
| Freeze batch, Mesen (60 runs) | 0 hangs | 60/60 `NOHANG`, 0 bad-DB interrupts |
| Bridge (Mesen) | pass | pass |
| Rumble, Mesen | pass | pass |
| Rumble, snes9x (base, var 0/101) | pass | pass |
| Rumble, snes9x var 37 | pass | S1 fail: no hit taken and no boss within 17000 frames (different fight). Var 36 and 38 pass |
| Outline, Mesen (full / carry only) | pass / pass | 1 fail (test 6: no goon on screen during the low-stamina window) / pass |
| Outline, snes9x | 9/9 | test 4 fail: no frames usable for silhouette coverage (`composedFrames` 0); 0 bad tiles, red outline present |
| Unit tests | 1644, 1 known failure (`test_chromatic_wub`) | 1652, same single known failure |

The outline and rumble failures depend on the scenario, not the audio engine.
With the same one- to five-frame input shifts, 4302 fails snes9x outline
tests 4 and 5 as well (`suite-4302-recheck/`), and the screenshots show
4303's Alex losing a fight that 4302's Alex wins.

### Audio vs NES and 4302 (solo-voice stems, three scenes)

- Duty: 12.5/25/50 % use matches the NES in both builds.
- Pulse timbre: 4303's pulse samples have sharper edges, closer to the NES
  square and brighter than 4302. About 5–10 % quieter overall.
- Noise: brighter than both. Median spectral centroid is about 2.5 kHz on the
  NES, 4.5 kHz on 4302 and 5.7 kHz on 4303, because there is no noise clock table.
- Triangle: **clicks**. The triangle stem has discontinuity spikes in
  70/93/246 frames (title/combat/mall) on 4303, against 0 on 4302. The
  triangle is cut to zero mid-wave (e.g. −1712 → 0 in one sample); 4302's
  triangle release avoids this.
- Sweeps: on the title music, the NES (and 4302) play pulse-1 drops of −200
  then −199 cents with a restart. 4303 plays a single −500-cent glide and
  detects 9 of 12 sweeps. In the mall it also adds glides the NES does not
  play (+327 and −810 cents).
- Mix-level clicks: NES 1 per scene, 4302 0, 4303 0/0/3 (mall, a noise plus
  pulse-2 effect onset).

## Recommendation

The switch is technically workable: the protocol is close to the old one, the
link is healthy and the sender costs about a third as much. For release audio,
port this project's own fixes (triangle release, noise clock table, sweep
driver, restart volume) onto the Project Nested base, then repeat these
comparisons (done in 4304, see below).

## Build 4304: Project Nested engine + this project's SPC extensions

### Approach

`tools/build_nested_ext.py` builds the engine. It assembles a patched copy of
Project Nested `Spc.asm` (pinned revision) together with
`tools/nested_spc/rcr_ext.asm` (project-owned glue) and the project's own
4302 driver block. `Dmc.asm` and `Spc.Memory.asm` are not assembled, so 4304
has no DMC heap, the same as 4302. The 4302 host sender and protocol are
unchanged. Only the engine image (at ROM `0x120000`), the upload length and
the checksum differ from 4302.

- **4302 extension block:** `$2F29–$3736` in 4302 is entirely
  project code, because Memblers' image ends in zero padding at `$2F29`. It
  holds the timed/staged receiver, the sweep kernel and driver, the publisher
  (KON staging, startup pitch, restart-volume delay) and the triangle
  attack/release envelope. The builder decodes it by reachability from its
  entry points and relocates it to the end of the Project Nested image
  (`$3050`). It remaps the four Memblers entry points it calls (square0,
  noise, check_timer3, reset) to the matching Project Nested labels and
  patches the freqtable immediates.
- **Hooks in `Spc.asm`:** each is an exact, single-match line-sequence
  replacement, and the build fails if a hook does not match.
  - Receiver: no `$BFFF` static read; transfers go through the timed receiver.
    The wait loop runs check_timer3 and then the staged-frame check.
  - Pulse: volume writes go to a dummy address because the publisher owns
    volume. A duty change stages KON through the publisher. The Project Nested
    pitch path is skipped because the sweep driver and publisher own pitch.
  - Triangle: silence and timer completion call the 4302 release (pitch 0,
    GAIN `$9F`). Note-on calls the 4302 attack (GAIN `$DF`). The sample switch
    no longer forces KON. Volumes are the same as 4302 (`$1F` / `$3F`).
  - Noise: the 4302 clock table (`3f3f3f3f3f3e3e3d3c3b3a383735322f`).
  - Timer 0 runs at 2 kHz (`$FA` = 4), as in 4302.
- **Sample variants (`rcr_ext.asm`):** Project Nested picks a pulse sample
  length by pitch. 4304 picks one only when a note is keyed on. During a note
  it holds that sample and rescales only the pitch, stepping down only if
  the pitch would overflow. Without this rule the title sweeps split into
  extra glides. Duty comparisons use Project Nested's SRCN layout.
- The sharper Project Nested pulse samples (closer to the NES square) are kept.

### Audio metrics (solo-voice stems; title / combat / mall)

`tools/audio_fidelity_metrics.py`. Evidence:
`~/rcr-evidence/nested-audio/metrics-4304-final.json` (stems in `stems/`).

| Metric | NES | 4302 | 4304 | 4303 (stock PN) |
| --- | --- | --- | --- | --- |
| Triangle mid-wave cutoffs | 1 / 1 / 1 | 0 / 0 / 0 | **0 / 0 / 0** | 104 / 144 / 382 |
| Mix-level clicks | 1 / 1 / 1 | 0 / 0 / 0 | **0 / 0 / 0** | 0 / 0 / 3 |
| Title pulse-1 sweeps matched to NES (median cents error) | 12 | 11 / 12 (1 c) | **11 / 12 (1 c)** | 9 / 12, merged −500 c glide |
| Title pulse-2 sweeps matched | 9 | 9 / 9 | **9 / 9 (2 c)** | — |
| Mall extra pulse-2 glides | 0 | 6 | **1** | +327 / −810 c |
| Noise spectral centroid, Hz | 2415 / 2525 / 2629 | 5705 / 4463 / 4473 | **5702 / 4465 / 4482** | ~5700 |
| Duty use | ref | matches | matches | matches |
| Pulse HF ratio >6 kHz (edge sharpness) | 0.023 / 0.016 | 0.0002 | **0.0063 / 0.0159** | sharp |
| Triangle RMS | ref | ref | = 4302 | — |

Title pulse-1 glides (cents), 4304 against the NES:
−601/−600, −198·−199/−200·−199, −601/−600, −186·−198/−500, −601/−600,
−199/−200·−199, −580/−535, −198·−199/−200·−199, −602/−600. The one mismatch
(NES −500 vs two steps) is the same as 4302.

Caveats:
- **Noise** equals 4302 but is still about 2× brighter than the NES centroid.
  The clock table already matches the NES clock rates. The remaining gap is
  high-frequency sidelobe energy, which the NES reference (fceumm output
  filter) removes and the SNES DSP does not. Getting closer would need a
  low-pass filter (for example, echo FIR) or slower clocks, which changes the
  timbre. This was not done.
- **Mall pitch alignment** equals 4302 up to the `right_15` step. After that,
  the gameplay in the capture runs diverges (screenshots differ from
  `right_16` on, the same as with 4303), so later mall numbers are not
  comparable. The mall ABC windows start at `right_05`.

### Suite (`~/rcr-evidence/nested-audio/suite-4304/`)

| Check | Result |
| --- | --- |
| Mesen spclink | 0 timeouts; 5386/5400 frames with a call, 6030/6030 returns; sender 18–46 scanlines (one outlier at 149; 4302: 135) |
| Mesen timing (default / Gamer) | max vblank line 257 / 257, 0 batches ending in active display (4302: 257/258) |
| Mesen rumble, bridge, accept, accept-onlycarry | all pass (fails=0) |
| Mesen variants | 60/60 NOHANG, 0 bad-DB interrupts |
| snes9x variants | 66 runs, 0 hangs |
| snes9x accept (outline) | base: fails 5, 6; var-1: pass; var-2: pass; var-5: fails 4, 5, 6 |
| snes9x rumble | base and var 0: fail S1, S4 (never reached pause: pauseFrames=0); var 36, 37, 38, 101: pass |
| Unit tests | 1659 run, 1 known failure (`test_chromatic_wub`), including `test_nested_ext` |

Input-shift tolerance: the snes9x outline and rumble scenarios depend on how
the fight plays out. With one- to five-frame input shifts, 4302 also fails
outline tests 4 and 5 (`suite-4302-recheck/`). Each failing check passes on
at least one shifted variant, and the failures that happen (no fight
contact, pause never reached) are scenario outcomes, not engine faults.

### ABC WAVs (`~/rcr-evidence/nested-audio/wav-4304/`)

Each file is 20 s each of NES (fceumm), then 4302, then 4304, with 1 s gaps,
at 48 kHz:
- `title-music-ABC-NES-then-4302-then-4304.wav`
- `street-combat-ABC-NES-then-4302-then-4304.wav`
- `mall-walk-ABC-NES-then-4302-then-4304.wav`

Full captures per build (`*-NES-fceumm.wav`, `*-SNES-4302-memblers.wav`,
`*-SNES-4304-projectnested-ext.wav`) and solo stems (`solo/`: mall triangle,
title pulse-1 sweeps, combat noise) are in the same folder.

### Artefacts

- ROM (not tracked): `build/nested-ext-4304/native-cpu.sfc`, SHA-256
  `369d0066273992a6f2e10bc3d1d32239ceb4e89a87f276a0f5b048404adfe9f0`
- Engine image: 13405 bytes (Project Nested part 11336, block base `$3050`),
  SHA-256 `f05ff5d4ec083e8768d82fb56e1946f96fb5d102bb245cd7bab237edf34f9b64`
  (pinned by `tests/test_nested_ext.py`)
- Not tested on hardware.
