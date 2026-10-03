# River City Ransom — NES to SNES

Native SNES port of the US NES game. Original game logic on the 65C816, NES
PPU/APU/MMC3 translated to SNES hardware, NES sound synthesized on the SPC700
(Memblers 2A03 engine).

**Playable experimental trial, not a release.** Candidate **4108**
(`build/timed-token-grace-game-4108/native-cpu.sfc`, SHA256
`57c62e5e9f5e6a112e6a72889beba87d85510bff40e5c3182533ef38f6653da7`) is the 1P
EverDrive gameplay trial. Splash trial **4146** (same gameplay, louder chromatic
WUB, SHA256 `d9955080c30ef2dad651894312250b3a468d669e84b7be397d0ca71d790b206a`)
is also on the card as `River City Ransom SNES 4146 splash.sfc`. 2-player combat
still hitches. Popping and NES-matched speed are not certified.

Offline 4108 gates (not a hardware certificate): full 9,092-frame route all
two-frame cadence; 1P combat including-busy; Present Status vs NES; shop
two-purchase; DMA envelopes. Notes:
[timed-token-grace](docs/TIMED-TOKEN-GRACE.md),
[roadmap](docs/ROADMAP.md),
[issues](https://github.com/struktured-labs/river-city-ransom-snes/issues).

Combined **4163**
(`build/ai-p2-4163`, SHA256
`bd62a39387e2281ffb9ab3038ab531a4bfbf6cf1aa9bcea1754146f16cd00ba0`) is 4162
difficulty plus AI: R toggles on settings or in-game, HUD **AI** label,
lane-first pathfinding. Emulator audit pass; on EverDrive as
`River City Ransom SNES 4163 AI Gamer.sfc`. Intermediate and Gamer Mode are
[locked](docs/GAMER-MODE.md): optional grind, Gamer-only speed>63, SRAM.
Original NES Advanced Simon is not an overflow-easier fight (#22): +16 with
63/127 caps. Player food is still the original 63/127. 44-char password
encode/decode is not in the ROM (`tools/rcr_password.py` only classifies
length). Controller presets (#12) are still open. Later `main` commits changed
the companion and splash without a new published hash. Branch `ai-p2-4225`
records candidate 4225 and is intentionally not merged.

ROMs, extracted assets and generated cartridges stay local. Start with
[visual audits](docs/audit/README.md) and the [development runbook](docs/DEVELOPMENT.md).
A static pixel match is never a gameplay pass.

Implemented:

- Strict iNES parsing and US RCR PRG/CHR checksum validation.
- Extraction of 16 × 8 KiB PRG banks and 128 × 1 KiB CHR banks.
- Lossless tile conversion to SNES 2bpp background and 4bpp sprite storage;
  original pixel indices are unchanged, added bitplanes are zero.
- 32 KiB LoROM startup, vectors, checksum, bounded SPC upload and frame transfer.
- Automated data tests and a headless libretro CPU/audio smoke test.
- Authenticated FCEUX instruction/hardware/RAM-code traces and screenshot captures.
- Trace-covered native CPU hooks, bank switching, RCR coroutine NMI adapters,
  PPU shadow/CHR reads, original-tile rendering, controller input and game APU transport.
- Incremental dirty-row publication, bounded VBlank DMA, and an asset-free
  two-generation graphics regression cartridge (background, sprites and bank switch).
- Hash-bound visual comparisons, negative controls, human review notes and receipts.

See [recorded validation](docs/VALIDATION.md), [research](docs/RESEARCH.md),
[architecture](docs/NATIVE.md) and [milestones](docs/ROADMAP.md).

## Build the audio diagnostic

Requirements: Python 3.10+, Git, Make and a C compiler. Bootstrap fetches pinned
cc65 and upernes sources into ignored `.deps/`; it does not install system tools.

```sh
make bootstrap
python3 -m pip install -r requirements-dev.txt
make verify
```

Output: `build/audio-bringup.sfc`. Open in Snes9x/Mesen or run the automated check
with a locally built Snes9x libretro core:

```sh
python3 tools/smoke_libretro.py --core /path/to/snes9x_libretro.so \
  --wav build/audio-bringup.wav
```

## Prepare your original game

```sh
python3 tools/rom.py inspect '/path/to/River City Ransom (USA).nes'
make prepare ROM='/path/to/River City Ransom (USA).nes'
```

Preparation accepts the US PRG CRC32 `78784CBF`, CHR CRC32 `204AA5EB`, mapper 4,
128 KiB PRG and 128 KiB CHR. It creates `build/assets/` and refuses to overwrite
an existing extraction. Inspection can report other clean iNES 1.0 images;
preparation rejects unrecognized revisions. ROMs and extracted assets stay local.

`make port` still refuses to imply a finished conversion. Named experimental
cartridges are rebuilt with `make playable` below. Audits follow
[the development runbook](docs/DEVELOPMENT.md).

## Rebuild a named playable trial

`BUILD` is `4108` (1P trial), `4146` (louder splash on that gameplay), `4162`
(Intermediate and Gamer on 4146), or `4163` (AI on 4162). The default is `4163`.
Each finished ROM is checked against the SHA-256 published above and in
`docs/GAMER-MODE.md` / `docs/TIMED-TOKEN-GRACE.md`.

```sh
make bootstrap
make playable ROM='/path/to/River City Ransom (USA).nes' BUILD=4108
make playable ROM='/path/to/River City Ransom (USA).nes' BUILD=4163
```

The US ROM is required and must be the image recorded in the parent manifest
(`source_rom_sha256`). It is not enough by itself. 4108's parent is early-OAM
build **3955** at `build/early-oam-live-half-game-3955/native-cpu.sfc`
(SHA256 `f6f69215716ecc077c9082da0a20db1eaaa064daab81b0992a54cade834d1e16`).
If that directory is absent, the same target will advance build **3800**
(`build/palette-reserve-absolute-game-3800/native-cpu.sfc`, SHA256
`6a01aa4269338cc90098fce914dd65c09b1f0618ea57c28e8de2549449c4d33e`) through the
exact-SHA builders up to 3955. Neither cartridge is in git (`build/` and
`*.sfc` are ignored). Without one of them, `make playable` exits and names
the missing files.

FCEUX title/walk traces are not an input to this target and are not committed.
`docs/DEVELOPMENT.md` still uses them for a generic `build_native.py` image.
That command does not emit 3800 or 3955; the prefix below 3800 is a further
chain of local exact-SHA patches (3780 and earlier) that only exist on a
machine that already built them.

Builds 4236 and gamer-eyes-4239, and a separate `snes/gamer_eyes.asm`, are
not in this repository or on any pushed branch. They are missing local inputs.
This target does not look for them and does not emit them. `snes/ai_p2.asm` on
`main` has an inline `gamer_eyes` routine; that is not those cartridges.

4146, 4162, and 4163 are produced from the builders at
`e4849b22be363338de681ec4678741c067e40890`, the commit that recorded 4163.
The tool checks out that revision under `build/` (gitignored) so later splash
and AI edits on `main` do not change those checksums. `make bootstrap` must
have run first (`ca65`/`ld65`).

FCEUX's palette, used by captures and `build_native.py`, defaults to
`/usr/share/fceux/palettes/FCEUX.pal`. Set `FCEUX_PALETTE` (and `FCEUX` for
the emulator binary) when it lives elsewhere.

## References and credit

Port development and automated validation by **struktured labs**, with thanks to:

- **infidelity** — NES-to-SNES porting inspiration and direct guidance on the
  8bpp splash-screen window-mask reveal. His work and advice inform this port;
  this is not an infidelity port or a claim that his game-port source is included.
- **Rumbleminze** — the
  [NES-to-SNES porting template](https://github.com/rumbleminze/nes-to-snes-template)
  informs the native CPU and hardware-translation design. Design/source
  inspiration; the template is not vendored here.
- **Memblers (Joey Parsell)** — author of the original **2A03 sound emulator
  for the SNES SPC700**, with assistance from Kevin Horton and others. Builds up
  to 4302 embed the copy retrieved through
  [upernes](https://github.com/mandraga/upernes).
- **Myself086 (Laurent Courville)** — the updated version of that engine in
  [Project Nested](https://github.com/Myself086/Project-Nested) (MIT), which the
  `nested-audio` trial (4303) assembles from source. Our integration and patches
  do not replace either upstream authorship credit.

See [third-party provenance](docs/THIRD_PARTY.md) for exact revisions, the sound
engine hash, and integration limits. These credits acknowledge contributions
and inspiration, not endorsement of this unfinished port.
