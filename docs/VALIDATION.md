# Recorded validation — 2026-09-14

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
No playable River City Ransom binary was built or tested.
