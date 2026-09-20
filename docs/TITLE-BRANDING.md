# Opt-in SNES port branding

`tools/brand_title.py` is a conservative first pass requested by the user. It
replaces the 29-character mode-selection instruction, `Select game mode &
character.`, with `SNES PORT BY STRUKTURED LABS.`. It preserves the original
Technos opening credit, all CHR artwork, palettes, and executable code. It is
**not** a new title-logo design and sacrifices that one menu instruction.
Default native builds remain unchanged. A later user-supplied visual reference
can inform a separate layout that retains the instruction too.

The authenticated US no-input capture goes from the Technos opening to the
1P/2P menu; this implementation does not claim to replace a separate NES-logo
title screen. No graphics from another Kunio game were imported.

The original text is at PRG offset `$F9FE`, corresponding to native cartridge
offset `$4B9FE` (CPU `C4:B9FE`). Existing uppercase glyphs are `$C0..$D9`, space
is `$00`, and period is `$B6`. The tool verifies the native image header,
checksum, exact unique preimage, source-ROM manifest binding, and unchanged
string length. It refuses an already-patched image. Only these 29 bytes and
the SNES checksum may change.

```sh
python3 tools/brand_title.py --candidate build/bulk-io-core-01 --out build/title-branding-02
python3 tools/check_title_branding.py --candidate build/bulk-io-core-01 \
  --branded build/title-branding-02 \
  --core /tmp/rcr-snes9x/libretro/snes9x_libretro.so \
  --reference build/reference-title-05 --out build/title-branding-audit-05
python3 -m unittest tests.test_brand_title
```

The audit runs fresh 600-frame no-input captures, checks the label pixel by
pixel against glyphs decoded from the authenticated original PPU snapshot,
requires a real visual change, verifies every pixel outside the footer is
unchanged, and requires byte-identical captured audio. Blank, wrong-glyph,
and outside-region changes have negative unit controls. HTML includes paired
screenshots and playable audio. This is scoped menu evidence, not a full
gameplay or speed certification.

## Separate splash direction (2026-09-15)

The user supplied a screenshot of direct guidance from Infidelity, describing
his own splash implementation: an 8bpp BG1 image revealed left-to-right using
window masking. Initialize `$2126` and `$2127` to zero, advance `$2127` by four
per frame, and stop at `$FC`. His accompanying setup uses zero BG1 scroll
(`$210D`/`$210E`), `$2123 = $03`, and `$212C` through `$212F = $01`.

This is a contextual implementation reference, not a complete standalone PPU
initialization recipe. The optional splash must establish its own display
mode, tiles, map, palette, and window configuration and restore the game's
display state on handoff. Automated coverage should check the reveal pixels,
frame progression, and the unchanged game presentation and audio afterward.
Use a separate boot splash so the original mode-selection instruction can
remain intact. This was the initial September 15 research direction; the
owner subsequently supplied artwork and the actual
[audited, hardware-tested boot splash](BRANDING-SPLASH.md) keeps the original
mode-selection instruction. The footer text substitution above is a distinct
historical prototype and is not included in the live ROM.

Initial candidate parent SHA-256:
`af7883ec4103688b637b55e43a07837cbe006adf7ee1f979d1e9381d7809cc95`.
Branded SHA-256:
`c39dae6bbf31aff129a4b5439c5ca3f8fc0039ac6656a2b3b959a1bba0476e7b`.
All four gates pass; 600 pixels differ, all inside the footer. NMI counters
at frames 300/600 remain 198/498. No Rivalmage deployment was performed.
