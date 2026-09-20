# River City Ransom — NES to SNES

Native SNES port of the US NES game. Original game logic on the 65C816, NES
PPU/APU/MMC3 translated to SNES hardware, NES sound synthesized on the SPC700
(Memblers 2A03 engine).

**Playable experimental trial, not a release.** Candidate **4108**
(`build/timed-token-grace-game-4108/native-cpu.sfc`, SHA256
`57c62e5e9f5e6a112e6a72889beba87d85510bff40e5c3182533ef38f6653da7`) is on
EverDrive / SNES Junior. 1-player street → mall → café → park runs; the owner
called hardware gameplay fantastic. 2-player combat still hitches. Splash WUB
is still too quiet versus in-game mix. Popping and NES-matched speed are not
certified.

Offline 4108 gates (not a hardware certificate): full 9,092-frame route all
two-frame cadence; 1P combat including-busy; Present Status vs NES; shop
two-purchase; DMA envelopes. Notes:
[timed-token-grace](docs/TIMED-TOKEN-GRACE.md),
[roadmap](docs/ROADMAP.md),
[issues](https://github.com/struktured-labs/river-city-ransom-snes/issues).

Next requested work: 2P AI (#2), splash sound (#13), controller presets (#12),
Intermediate difficulty (#20), ultra-hard Gamer Mode (#21). Original NES
Advanced Simon is not an overflow-easier fight (#22): skill is +16 with 63/127
caps (stamina 118→127, will stays 63). Splash trial 4146 is louder chromatic
WUB, not flashed.

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

`make port` still refuses to imply a finished conversion. To reproduce the
experimental cartridge and audits, follow [the development runbook](docs/DEVELOPMENT.md).

## References and credit

Port development and automated validation by **struktured labs**, with thanks to:

- **infidelity** — NES-to-SNES porting inspiration and direct guidance on the
  8bpp splash-screen window-mask reveal. His work and advice inform this port;
  this is not an infidelity port or a claim that his game-port source is included.
- **Rumbleminze** — the
  [NES-to-SNES porting template](https://github.com/rumbleminze/nes-to-snes-template)
  informs the native CPU and hardware-translation design. Design/source
  inspiration; the template is not vendored here.
- **Memblers (Joey Parsell)** — author of the **2A03 sound emulator for the
  SNES SPC700** used by this project, with assistance from Kevin Horton and
  others. The pinned engine is retrieved through
  [upernes](https://github.com/mandraga/upernes); our integration and experimental
  patches do not replace that upstream authorship credit.

See [third-party provenance](docs/THIRD_PARTY.md) for exact revisions, the sound
engine hash, and integration limits. These credits acknowledge contributions
and inspiration, not endorsement of this unfinished port.
