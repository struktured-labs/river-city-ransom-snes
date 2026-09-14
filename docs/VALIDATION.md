# Recorded validation — 2026-09-14

## Current native checkpoint

This is development evidence, not a finished-port certification.

- `make verify`: 18 tests pass, including attribute quadrants, flipped tall
  sprites, geometry and one-pixel negative controls, NMI reset/fault detection,
  coroutine tail hooks and the self-modifying audio operand.
  Gallery tests reject image tampering, forbidden ROM payloads and a false live pass.
  Native assembly tests catch the accumulator-width and unmapped-WRAM regressions.
- Generated review JavaScript passes save/reload/export contract checks and
  starts new evidence unreviewed. Gallery integrity also covers the collage and
  HTML, not only individual screenshots. This is not a browser-layout test.
- Asset-free native adapter cartridge: executes the production PPU write/read,
  CHR-bank read and register/direct-page preservation code in Snes9x. The positive
  case passes with advancing counters; a deliberately corrupted CHR byte fails
  the expected CPU-side assertion. CI runs both controls without the RCR ROM.
- Renderer fixtures: logo at NES frame 120 and menus at 300/600 each have zero
  mismatched pixels over 61,184 pixels at RGB555 precision; raw RGB error ≤5.
  The 240th NES row is explicitly outside the 239-row SNES comparison viewport.
- Actual native execution reaches menus and street. An earlier no-audio native
  menu matched exactly; the current fixed audio-enabled checkpoint differs by
  16 blinking-cursor pixels, reported as a mismatch without masking/alignment.
- 12,000-frame native scripted-input soak: NMI advances at all 40 checkpoints
  (71 → 6557), no unknown-I/O or SPC timeout, NMI depth ≤1, audio peak 1846.
  This proves adapter liveness, not full gameplay or sound equivalence.

Current cartridge SHA-256:
`c03c27a625d91c268f6bbbb958db256bf2f8dcf8a06804ee37809dbd340129b1`.
See [audit evidence](audit/README.md) for exact identities. Live comparisons are
not frame/input synchronized. Scrolling, raster HUD, speed, full mapper coverage,
two-player/shops/transitions/ending, sound accuracy and physical SNES are unverified.

The current core is Snes9x revision below **plus** `tools/snes9x-debug.patch`,
not stock. Its SHA-256 is
`2e05b2f9a24293fbcdd030d8c117d067dda9533025896365685078d07a1a22e5`.
The patch exposes registers and opt-in traces. `tools/bootstrap_core.py` reproduces
that source state; compiler/platform changes require new core receipts.

## Historical initial diagnostic (before native integration)

`make bootstrap` fetched the pinned revisions and built ca65/ld65 successfully.
`make verify` assembled and linked the 32 KiB SNES diagnostic, verified its
header/reset vector/checksum and passed all six automated test cases. Tile tests
decode and compare every pixel of 256 deterministic synthetic tiles at both
output depths; no original game assets are required by these tests.

Snes9x source revision `7a8878f1306f65594c30b7d86dee41d972c2e495` was built as a
libretro shared library. Command:

```sh
python3 tools/smoke_libretro.py \
  --core /tmp/rcr-snes9x/libretro/snes9x_libretro.so \
  --wav build/audio-bringup.wav
```

Result: 300 emulated frames, 300 video callbacks, WRAM status `01`, frame counters
131 and 280 at the two checkpoints, nonconstant audio with peak amplitude 2309
at 32040 Hz. The test excludes startup audio when checking for sustained sound.
The roughly 20-frame startup interval includes transferring the SPC engine.

This validates the native startup and legacy Memblers engine transport in one
emulator. It does not establish game compatibility, audio fidelity for the game,
graphics equivalence on the original assets or operation on physical SNES.
At this initial checkpoint, no gameplay binary had been built or tested.
