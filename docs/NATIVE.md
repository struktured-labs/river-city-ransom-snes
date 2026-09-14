# Native integration notes

This is native 65C816 execution of the original PRG, not an NES emulator wrapped
in an SFC extension. Original assets are transformed only into SNES tile formats.
The experiment is intentionally narrow: traced paths are patched, not every
possible hardware access in the entire game.

## Cartridge and runtime

The 2 MiB HiROM uses C0 for bootstrap; C1–C8 each contain a 16 KiB selectable
PRG pair plus the fixed final 16 KiB. Hardware helpers and stubs are replicated
in every program bank. DB81–88 provide original low-RAM/I/O mirrors and banked
ROM data. Game code runs in 6502-compatible emulation mode. Runtime code switches
to native mode for SNES publication and restores the original register/stack ABI.
C9–CA hold original-index 2bpp tiles, CB–CE their zero-extended 4bpp equivalents,
and CF–D0 raw CHR for game data reads. The build validates the original US image.

The $1B00 mailbox and $1C00 adapter state are outside NES RAM. $7F0000–3FFF is
the software PPU shadow; $7E1000 is the NES OAM shadow. Native tilemap/OAM staging
uses explicit long WRAM addresses, not unmapped bank-zero $3000–3FFF.

## Bugs worth keeping in the regression record

- RCR's FC60 wait routine is a coroutine: FF61 discards an interrupt frame and
  returns to FC60's caller. A normal JSR hardware hook around the PPUCTRL enable
  breaks its stack. Those sites use per-PC tail hooks with the original stack
  shape at interrupt enable; NMI return paths have explicit adapters.
- The sound driver writes `STA $40xx; RTS` into RAM at $07F8 and jumps there.
  PBR C6:$07F8 is cartridge ROM on SNES, not CPU RAM. The traced jump is redirected
  to a helper that reads the self-modified operand and transports the APU write.
- PPUDATA reads are not just graphics readback: RCR stores nametable data in
  CHR ROM. Omitting MMC3-mapped CHR reads produced an almost-empty menu.
- ca65 accumulator-width annotations are compile-time state, not inferred from
  call sites. A missing `.a8` on a color helper corrupted its instruction stream.

## Current limits

The native publisher updates every 16 game NMIs and can force blank for large
CHR transfers. Its speed is not NES-equivalent. It selects one nametable, lacks
scroll/raster IRQ translation and native 8×16 sprite support, and assumes paired
MMC3 PRG switches. Mirroring, clipping, emphasis, sprite edge cases and mapper
mode changes need fuller implementation. IRQ activity is counted, not serviced.

APU writes and register-write retrigger flags reach the pinned legacy Memblers
engine. Sustained PCM and handshake success establish transport only. Host-side
length counters, envelope/sweep behavior, frame sequencing and DMC fidelity are
not verified. Do not claim cycle-accurate NES audio or physical SNES compatibility.
