# Palette alias investigation

## Implemented address correction

`build/palette-alias-01/native-cpu.sfc` SHA-256:
`a8f53e3211ba41e4c6e50c300b0a09acc3b5b2e524bedf8aed1e32453c31ad83`.
The production pointer now wraps palette indices at 32 bytes and aliases
`$10/14/18/1C` to `$00/04/08/0C`. Other memory regions are unchanged.
Case 20 writes through each of the 256 addresses in `$3F00..$3FFF`, then
reads both its independently calculated canonical address and its alias.
It failed on the uncorrected adapter. The positive adapter suite passes;
an automated mutant bypassing palette mapping fails specifically at case 20.

Prior bulk writer/reader fixtures expected independent bytes at `$3F20`,
`$3FFF`, and `$3F21`; their backing-address expectations are corrected.
The stride-32 ring test checks the final eight writes alias one byte and
the last write wins. Palette test entry resets the PPUADDR latch explicitly.
All 82 unit tests and the graphics suite pass.

Full retained-frame baseline `build/palette-alias-quality-01/snes` completes
in 2039 frames (2038 before this change). Its `site/index.html` report passes
settings and initial street background pixel gates, adapter safety and audio
presence gates. All four original-speed transition gates still fail; audio
fidelity and physical-hardware audio remain unverified. Not deployed.

Only address aliasing is corrected here. Palette write high-bit masking,
grayscale/open-bus reads, palette-read nametable buffer refill, and bulk
page-fill bypass behavior still require their own coverage. This is not a
claim that every palette semantic or the user's shop scene is fixed.

## Original finding and remaining investigation

Subsequent work in `build/palette-buffer-01` corrects palette-read refill to
the underlying logical `$2Fxx` shadow, preserving the original low address
rather than its palette alias. Executed case 21 covers all 256 low addresses
and checks the next non-palette read returns that refill. The old code fails
case 21; the corrected full adapter suite passes, and an automated wrong-page
mutant fails case 21. All 82 unit tests pass. This is a logical-shadow refill
fix, not full physical nametable mirroring: `mirror_write` currently records
`$1C18`, but `ppu_pointer` does not use it. Mirroring needs separate tests and
coordinated renderer changes. No hardware deployment.

Code inspection on 2026-09-15 found that `ppu_pointer` in
`snes/native_runtime.asm` masks the address to 14 bits but otherwise maps
palette addresses directly into the PPU shadow. Consequently `$3F10` and
`$3F00` are independent shadow bytes, and `$3F20` does not alias `$3F00`.
`prepare_palette` reads only the first 32 bytes at `$7F3F00`.

The pinned original-game emulator's `A2007` and `B2007` implementations in
`.deps/fceumm/src/ppu.c` provide a contrasting executable reference: palette
indexing wraps at 32 bytes, and entries with low two bits zero alias across
the sprite/background halves. `$3F10` accesses the universal backdrop
entry. Its internal replicated background colors are a renderer detail,
not a reason to alias all four background palette entries in CPU reads.

The targeted regression exercises both reads and writes across `$3F00..$3FFF`,
including `$3F10/14/18/1C`, repeated 32-byte mirrors, and address increments.
It uses production adapter entry points and a deliberately disabled
alias negative control. Palette reads also need a separate audit of their
nametable-backed read-buffer refill; the current adapter simply puts the
palette byte into its read buffer. Avoid bundling an unverified broad memory
rewrite into the loading guard.

These missing semantics are not yet proven to cause the user's shop colors:
we still need a capture of that scene or its actual palette-write sequence.
Likewise this does not explain fragmented mall NPC tiles by itself.

## Input-only route exploration

`traversal-upper` adds 90 frames of Up after the recognized street/settle
prefix, then preserves the existing 36 rightward 120-frame phases. No game
RAM, save state, speed override or collision bypass is used. Its unit test
checks the common prefix, exact added input, and unchanged rightward suffix.

`build/upper-lane-01/{nes,snes}` captures completed in 5602/5704 display
frames with every frame retained. The final screenshots show encounters in
the school area, not the mall. This route therefore does not reproduce the
reported shop failure. Do not call scenario completion a room-reached gate
or compare these differing encounter states as a controlled speed result.
