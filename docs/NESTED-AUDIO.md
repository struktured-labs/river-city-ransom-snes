# Trial: Project Nested SPC engine (build 4303, branch `nested-audio`)

Goal: replace the Memblers 2A03 SPC700 engine copy taken from upernes (SHA-256
`4e095134…`, no established licence) with the updated version of the same
engine in Myself086's Project Nested, which is MIT-licensed.

Status: **trial**. Build 4302 is still the release candidate. 4303 works, but
stock Project Nested loses the SPC fixes that this project added on top of
Memblers' engine (see Audio results).

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
comparisons. Get Memblers' written confirmation that the Project Nested version
may be used under MIT, and keep it with the release records.
