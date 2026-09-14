# River City Ransom — NES to SNES

Work in progress toward a native SNES port of the US NES game. Preserve the
original graphics, gameplay, music and effects. Run the game logic on the 65C816,
translate NES hardware operations, and synthesize NES sound on the SPC700.

**Experimental port, not release-ready.** Original game code now boots on the
SNES CPU, reaches the menus and street, accepts input, and sends game APU writes
to Memblers' SPC700 NES sound emulator. Scrolling, raster interrupts, timing,
audio fidelity and full-game compatibility remain incomplete.

Start with the [visual audit and collages](docs/audit/README.md). Renderer fixtures
and live execution have separate evidence: a static pixel match is never called
a gameplay pass. ROMs, extracted assets and generated cartridges stay local.

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

`make port` still refuses to imply a finished conversion. To reproduce the
experimental cartridge and audits, follow [the development runbook](docs/DEVELOPMENT.md).

## References and credit

Rumbleminze's [porting template](https://github.com/rumbleminze/nes-to-snes-template)
informs the native CPU plus hardware translation design. Infidelity's published
NES-to-SNES development discussion informs the porting approach; no public
assembly source from Infidelity was located during this research. Memblers
(Joey Parsell), with assistance from Kevin Horton and others, authored the
SPC700 sound engine used here, retrieved from
[upernes](https://github.com/mandraga/upernes). See
[third-party notes](docs/THIRD_PARTY.md) for exact revisions and integration limits.
