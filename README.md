# River City Ransom — NES to SNES

Work in progress toward a native SNES port of the US NES game. Preserve the
original graphics, gameplay, music and effects. Run the game logic on the 65C816,
translate NES hardware operations, and synthesize NES sound on the SPC700.

**This repository does not yet contain a playable port.** The current executable
is a hardware/audio diagnostic: a green screen and a sustained NES square wave.
It boots a real SNES ROM and uploads Memblers' 2A03 sound emulator. Red means the
SPC handshake timed out. No River City Ransom program or artwork is in this test.

Implemented:

- Strict iNES parsing and US RCR PRG/CHR checksum validation.
- Extraction of 16 × 8 KiB PRG banks and 128 × 1 KiB CHR banks.
- Lossless tile conversion to SNES 2bpp background and 4bpp sprite storage;
  original pixel indices are unchanged, added bitplanes are zero.
- 32 KiB LoROM startup, vectors, checksum, bounded SPC upload and frame transfer.
- Automated data tests and a headless libretro CPU/audio smoke test.

The MMC3 mapping, game entry points, PPU translation, controller hooks, IRQ/NMI
bridges and game audio write translation remain to be implemented against the
original ROM. See [research](docs/RESEARCH.md) and [milestones](docs/ROADMAP.md).

## Build the audio diagnostic

Requirements: Python 3.10+, Git, Make and a C compiler. Bootstrap fetches pinned
cc65 and upernes sources into ignored `.deps/`; it does not install system tools.

```sh
make bootstrap
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

`make port` currently fails explicitly: it cannot yet generate the game.

## References and credit

Rumbleminze's [porting template](https://github.com/rumbleminze/nes-to-snes-template)
informs the native CPU plus hardware translation design. Infidelity's published
NES-to-SNES development discussion informs the porting approach; no public
assembly source from Infidelity was located during this research. Memblers
(Joey Parsell), with assistance from Kevin Horton and others, authored the
SPC700 sound engine used here, retrieved from
[upernes](https://github.com/mandraga/upernes). See
[third-party notes](docs/THIRD_PARTY.md) for exact revisions and integration limits.
