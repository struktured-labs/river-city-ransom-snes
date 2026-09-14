# Research notes — 2026-09-14

## Cartridge target

[NesCartDB's physical US cartridge record](https://nescartdb.com/profile/view/241/river-city-ransom)
identifies NES-TLROM-02, MMC3A, mapper 4, 128 KiB PRG, 128 KiB CHR, no battery
and no cartridge WRAM. It reports PRG CRC32 78784CBF and CHR CRC32 204AA5EB.
The build validates these component checksums rather than a header-dependent
whole-file checksum. US NTSC is the initial target; other regions need separate
profiles and timing work.

## Reference ports

[Rumbleminze's template](https://github.com/rumbleminze/nes-to-snes-template/tree/64958b6bb21d348d18e40f60e7bb110faae98d3f)
provides concrete source for native 65C816 execution, bank-local routines,
PPU/OAM/palette translation and SPC integration. Its README explicitly requires
porting game-specific changes. The checked-in reset routine contains Castlevania
addresses; the extraction utility also contains game-specific offsets. Those
values are not RCR entry points and cannot be reused without analysis.

[Rumbleminze's own account of sound integration](https://forums.nesdev.org/viewtopic.php?t=24956)
describes following Infidelity's Mega Man IV approach, using Memblers' engine,
and finding the compiled engine and translation routines in upernes. Memblers
recommends the version improved by Myself086 in that discussion.

[Infidelity's development thread](https://forums.nesdev.org/viewtopic.php?p=270584)
is a primary reference for the NES-to-SNES workflow and use of Memblers' sound
emulator. A public Infidelity assembly repository was not located. This project
does not claim to have inspected unavailable source or to reproduce his ports.

## Sound choice and limitations

[upernes](https://github.com/mandraga/upernes/tree/d484e533bbd8335f9e0c6cc9272470f39c371419)
contains the legacy Memblers engine and a host implementation in
`source/asm/Sound.asm`. The pinned binary is 0x2C00 bytes, loaded and entered at
SPC address $0400. The diagnostic implements that engine's $7D/$D7 ready exchange
and 23-byte packet with acknowledgements on port $2140.

The newer engine in Rumbleminze's template uses different transport details
(including port $2141 acknowledgements), event/control flags and DPCM sample
preparation. Its binary is not a drop-in replacement. The first diagnostic uses
the older documented pair to establish an independently testable baseline.
Upgrading requires testing the engine and matching host translation together.

NES APU registers cannot just be copied once per frame and declared accurate:
same-value timer/length writes can retrigger notes, $4015 enables gate channels,
sweeps/envelopes/length counters need their proper clocking, and DMC needs sample
handling. The diagnostic exercises a sustained pulse only. It does not yet
translate the game's sound driver, validate all channels or provide cycle-exact
2A03 output. The game should retain its existing music and effect routines.

The desktop C++ [Nes_Snd_Emu](https://github.com/jamesathey/Nes_Snd_Emu) is a
different library; its PCM synthesis API is not an SPC700 runtime. Memblers'
engine is the SNES-oriented option appropriate to the requested architecture.

## Disassembly availability

[NES-Games-Disassembly](https://github.com/cyneprepou4uk/NES-Games-Disassembly)
lists River City Ransom in WIP with whole-file CRC C3508F7E. Inspection of its
current main tree and branch list found no River City Ransom source directory.
A WIP README entry is not available source. The local workspace and project
filename search also did not locate an RCR ROM. Actual vectors and game code
must be extracted from the user's original copy before gameplay porting.

## Implementation decisions

Preserve every CHR pixel index. Interleave the two NES planes for SNES background
tiles and append zero planes for SNES OBJ tiles. Preserve sprite geometry,
flipping and palette selections when the renderer is implemented. Palette RGB
conversion needs a documented reference because NES composite colour has no
unique lossless RGB equivalent. Do not introduce replacement art or MSU music.

The final game layout remains undecided pending PRG analysis. The diagnostic's
single-bank LoROM is only a hardware test. Determine RCR's actual MMC3 PRG mode,
bank pairs, CHR mode, mirroring writes and IRQ schedule from code and runtime
traces before choosing fixed-bank replication versus WRAM mapping.

PPU scroll/address latches, buffered reads, attribute quadrants, OAM conversion,
8x16 sprite addressing and split-screen timing need dedicated implementations.
Executing unmodified NES writes to $2000-$2007/$4000-$4017/$8000-$FFFF on SNES
will not run the game. Likewise, native 65C816 interrupt frames differ from 6502
frames: entry/return adapters must preserve stack semantics and register widths.

Acceptance requires matched NES/SNES input recordings across title, play,
two-player mode, shopping, transitions and ending, frame comparisons using a
fixed palette, audio comparisons and eventual real SNES testing.
