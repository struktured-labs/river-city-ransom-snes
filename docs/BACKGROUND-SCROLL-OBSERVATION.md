# Background scrolling: 748 positions verified without hiding sprites

Current game ROM is unchanged: `build/pending-palette-queue-327/native-cpu.sfc`,
SHA-256 `4339df2e5613e0d5af4ec7aa7e3888b991311281988b75a838f992e9e6d3a958`.
**No hardware deployment or restart.** This closes the sampled background
scrolling evidence gap, not full-game speed, combat, loading or audio acceptance.

## Result

`build/background-sweep-339` passes at the **same 748 first-stable camera
samples** used by the primary-image sweep: rooms 0/1/2/3 have 259/83/110/296
common positions. The minimum remains 64 per room. Every selected observer
row is supported; none is dropped or replaced by a later image.

- Zero RGB555 differences in the original fixed x=0..255, y=32..79 band.
- Zero differences in the **larger** fixed y=32..191 playfield band:
  30,638,080 pixel comparisons across the four rooms.
- No late scroll publications; second-consecutive stable samples no later
  than the original at those camera positions.
- Every pre-existing timeline field and every PCM sample matches the
  corresponding independent normal-core replay on both systems.
- The known broken-scrolling ROM (`paired-game-01`, SHA-256
  `c06511b87e82b8daf184b9016e14b86396aa90588033d2ec89467b553208ae21`)
  still completes the route and has sufficient coverage (593 positions),
  but fails with 16 differing background samples and 999 late publications.
  Its failure is not merely a timeout or insufficient coverage.

The original full screenshots still differ at 15 park positions because
jumping Alex enters the fixed comparison band. Those comparisons and
unchanged screenshots remain visible. The new collages show original output
and its background plane side by side, rather than erasing actors from an
image, realigning frames, or dynamically masking comparison pixels.

## Observation mechanism

The NES core copies its actual background pixels immediately before
`CopySprites`, retaining its real PPU scroll, CHR/nametable fetches and palette
indices. It converts through the same frontend palette as normal video.
It rejects grayscale/emphasis rather than approximating unsupported timing.

The SNES core reconstructs mode-0 BG1 from actual emulated VRAM, the
brightness-adjusted CGRAM lookup, and the real renderer's per-line scroll
and clipping intervals at each rendering flush. It handles tilemap sizes,
palette selection, horizontal/vertical flips, VRAM wrapping and BG windows,
including the NES left-eight-pixel mask. It rejects unsupported modes,
color math, interlace/hires, mosaic and nontrivial backdrop clipping.

Both observers write only additional host buffers. They do not write
emulated RAM/registers, alter the primary video buffer, disable sprites,
change inputs, or modify emulated cycle counts. Resetting an observation
clears validity and output, so missing scanlines cannot silently reuse a
previous frame. The normal core binaries remain unchanged.

## Independent observer qualification

`build/background-window-oracle-338` contains **80 executed asset-free cases**:
78 exact observer-versus-real-renderer comparisons and two unsupported-effect
rejections. The cartridge enables only BG1, making its entire ordinary
256×239 output an independent expected result. Coverage includes:

- all four tilemap layouts;
- fine scroll, 255/256/511 boundaries, both axes;
- three CHR bases, including VRAM address wrapping;
- distinct non-symmetric patterns, all palettes and flips;
- full/dim brightness and six normal/inverted/window-boundary cases.

The audit does not trust the saved pass flag alone. It rechecks the full
case matrix, source hashes, exact observer core, 120-frame execution
receipts, ROM/image/validity-file hashes, dimensions, and every output pixel.
The negative game uses that same qualified SNES observer core.

423 Python tests pass, including rehashed invalid source/image/row/path
bindings and strict observer neutrality. Existing café and primary-image
policies remain unchanged. `git diff --check` passes.

## Reproduction and provenance

Observer captures:

- NES: `build/background-nes-333` (8,548 frames), normal
  `build/park-single-nes-331`.
- SNES: `build/background-window-snes-336` (8,946 frames), normal
  `build/park-single-normal-331`.
- Broken control: `build/background-scroll-negative-336` (8,629 frames).

Observer core hashes:

- FCEUmm: `ef81caa5fb775d55f44b21cfa52cee319c45e2972bf3f52042a1e4cae1c0b55d`.
- Snes9x: `0c373ccc157ebaf2712061cdba0a171a173d5b6334b7bc9bc6336f63976b7d48`.

The two `tools/*-background-observer.patch` files preserve the integration
changes to the existing project diagnostic cores; reverse-application checks
pass against the installed sources. The FCEUmm patch assumes the existing
project frame/MMC3/CIRAM observer changes. Build additional targets, never
overwrite the pinned normal cores:

```sh
make -C .deps/fceumm -j4 TARGET=rcr_background_libretro.so
make -C .deps/snes9x/libretro -W ../gfx.cpp -j4 TARGET=rcr_background_window_libretro.so
```

Use `benchmark_capture.py --background-telemetry` with
`--scenario traversal-park-single-sweep` (also `--ppu-telemetry` for NES).
Run `check_background_observer.py` on the SNES observer core, then
`audit_background_sweep.py` with the observer/normal captures, oracle report,
and broken-ROM control. Complete hashes are in capture and audit receipts.

Retained intermediate evidence: the initial SNES observer rejected all game
bands because it supported no windows (`background-snes-333`), although its
48 asset-free comparisons passed. The first oracle link attempt also exposed
an extra header byte and was corrected before execution. Neither intermediate
result is a claimed game pass. `background-sweep-337` used the earlier
56-case qualification; 339 supersedes it with the fully revalidated 80 cases.

## Still open

Rooms 1/3 still load late (9/7/9 first scenery versus NES 7/7/7); the longer
combat route still diverges and the SNES character dies. Adaptive route
durations are not a same-input speed ratio. Packet cadence is not sound
synthesis or physical pop-free certification. Next work returns to these
remaining runtime/encounter problems; no acceptance threshold was weakened.
