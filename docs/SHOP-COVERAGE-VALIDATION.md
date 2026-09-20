# Café menu: reproduced and corrected hardware-access coverage

`traversal-shop` extends the mall route with 88 Right frames, 180 Up and
180 idle. Both systems reach Rise & Shine Cafe by controller input only.
The earlier 60-Right attempt stopped short of the door and is retained in
`build/shop-route-01`; it is not shop evidence. The settled checkpoint keeps
original RAM `$42=2`, so room number alone cannot establish shop arrival.

Original evidence: `build/shop-route-02/nes` (6,320 frames), with read-only
MMC3 observer. Broken candidate: `build/shop-route-02/snes` (6,458 frames).
The latter reproduces missing menu text, gray panels and red background.
Both select CHR R0–R5 `[124,126,112,113,114,115]`; unlike the mall NPC issue,
the settled CHR bank choice is already correct.

Replaying the original inputs through FCEUX for 6,600 frames creates
`build/reference-shop-01`, source-ROM and execution-file hash bound. Adding
this coverage patches 34 more executed hardware accesses (208 → 242; shared
stubs 43 → 44), including shop PPU status/address/data paths and additional
mapper writes. It is not a guessed scan of unexecuted ROM data. No renderer
palette workaround was added: the missing original writes now run through
the existing adapter. This combined coverage fixes the observed menu; it
does not isolate which individual access accounts for each visual symptom.

## Reproduction

```sh
python3 tools/build_native.py --experimental-fastrom \
  --trace build/reference-title-05 --trace build/reference-walk-02 \
  --trace build/reference-inventory-02 --trace build/reference-walk-long-01 \
  --trace build/reference-mall-02 --trace build/reference-shop-01 \
  --out build/shop-coverage-01
```

Candidate SHA: `0b0f72886a26948aec04cc8037a7f6093b5949e8378562ab21353824adc3c1e3`.
Replay: `build/shop-coverage-route-01/snes`, 6,458 frames, complete and
fault-free. `tools/check_shop.py` checks hash-bound captures and delivered
inputs, exact shop CHR selection, settled uploads, and RGB555 pixels in the
fixed `(90,56)-(248,166)` menu rectangle. There is no image search/alignment.

All **17,380 menu pixels match** the NES reference. The old build differs
at all 17,380 and fails the same check. Reviewable complete-frame collages:

- `build/shop-coverage-audit-01/index.html` — corrected, all gates pass.
- `build/shop-coverage-negative-01/index.html` — old build, correctly rejected.

Complete frames retain actor/HUD differences; 283 pixels below y=32 differ
outside the passing menu rectangle. Do not interpret the menu gate as a
whole-screen or all-shops equivalence claim. Route-prefix/input tests and
fixed-coordinate/color-precision unit tests pass; total suite: 99 tests.

Baseline replay `build/shop-coverage-quality-01/snes` remains 2,074 frames.
No original-speed or audio-popping pass is claimed. Other shops, purchases,
shop exits, full scrolling and audio fidelity remain to be tested. The port
still depends on exercised execution coverage; unvisited paths can contain
more unpatched accesses. No Rivalmage deployment or original-art changes.
