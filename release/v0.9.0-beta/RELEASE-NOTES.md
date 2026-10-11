# DRAFT: GitHub release (not created)

- **Tag:** `v0.9.0-beta`, on the merge of `release-1.0-prep`. If the release is cut
  before merging, tag commit `release-1.0-prep` HEAD instead. The ROM is build 4304
  (`nested-audio`, `tools/build_nested_ext.py`): build 4302 with the Project Nested
  SPC engine plus this port's SPC fixes.
- **Title:** River City Ransom SNES v0.9.0 beta
- **Pre-release:** yes
- **Assets:**
  - `river-city-ransom-snes-v0.9.0-beta.zip` (the two patches, README.md, CHECKSUMS.txt, THIRD-PARTY-NOTICES.txt)
  - `river-city-ransom-snes-v0.9.0-beta.bps` (178,550 bytes; also attached on its own)
  - `river-city-ransom-snes-v0.9.0-beta-headerless.bps` (178,441 bytes; also attached on its own)
  - Never attach a ROM (.nes or .sfc).
- **Visibility:** the repository is currently **private**. Release assets are public
  only if the repository is made public, or if the release is published from a public
  repo such as a new `struktured-labs/river-city-ransom-snes-releases`. Download link
  once public: https://github.com/struktured-labs/river-city-ransom-snes/releases/download/v0.9.0-beta/river-city-ransom-snes-v0.9.0-beta.zip

---

## River City Ransom SNES v0.9.0 beta (build 4304)

A native Super Nintendo port of *River City Ransom* (NES, 1989). The original game
code runs natively on the 65816. Graphics are converted for the SNES PPU, and the NES
music and sound effects play through the SNES APU using Memblers' 2A03 SPC700 engine,
in Myself086's updated Project Nested version, with this port's own audio fixes.

**The download is a patch only.** Apply it to your own `River City Ransom (USA).nes`
(No-Intro; file CRC32 `C3508F7E`, SHA-1 `A8612A36D9D2739D2B321B6EBB97C2757CCCA410`,
with the iNES header). A headerless variant is included (ROM CRC32 `E9C387EC`).

### Highlights
- Native SNES port (2 MB HiROM, FastROM).
- New difficulty levels: **Intermediate** and **Gamer**. Gamer gives enemies +32,
  raises the 127/255 stat caps, and makes agility above 63 actually faster. The
  original Novice and Advanced are unchanged.
- A red **gang outline** on Gamer.
- **Rumble** on controller 1 with the MiSTer SNES core (20260603+, SNAC off).
- **MiSTer savestates** work, and the Limited Run SNAC controller works on MiSTer.
- Audio: Project Nested SPC engine with this port's fixes (NES-matched pitch sweeps,
  click-free triangle, NES-rate noise clocks); crisper pulse channels.
- struktured labs boot splash.

### Patched ROM
`CRC32 816D398D` · `SHA-1 7CF7E984A8165684DBE2CA752CBA23FE92BFCD7B` ·
`SHA-256 369d0066273992a6f2e10bc3d1d32239ceb4e89a87f276a0f5b048404adfe9f0` · 2,097,152 bytes

### Tested on
Mesen2 2.1.1 and snes9x (libretro): all automated checks pass. Earlier builds of this
port were played on MiSTer and an EverDrive; builds 4299 (SNAC controller) and 4301
(savestates) were checked on MiSTer. **Build 4304 still has to be confirmed on
MiSTer and on real hardware.**

### Known issues
Occasional audio pops or silence (#6); speed is not NES-certified and there are
two-player hitches (#5); transient sprite glitches (#8); shop text and colour
differences (#9, #16); blank Present Status values (#4); SRAM keeps only the difficulty setting, and there are no extended
passwords yet. The AI Player 2 companion is not in this build.

See `release/v0.9.0-beta/README.md` for controls, credits and the full changelog.

### Credits
struktured labs. The 2A03 SPC700 engine is by Joey Parsell (Memblers), with Kevin
Horton and others, in the updated version from Myself086 (Laurent Courville)'s
Project Nested (MIT licence; notice in the zip). upernes (Patrick Areny) was the
reference for NES-on-SNES audio delivery. Thanks to Rumbleminze, infidelity,
the Limited Run Games SNES Rumble protocol, and the MiSTer SNES core developers.
*River City Ransom* © Technōs Japan / Arc System Works. This is an unofficial fan
project, and no ROM data is distributed.
