# Reproducing the experiments

Prerequisites: Python 3.10+, Make, C/C++ compiler, Git, FCEUX 2.6.5 with Lua,
Xvfb/xvfb-run, and FCEUX's `FCEUX.pal`. Capture and `tools/build_native.py`
default to the Debian paths `/usr/games/fceux` and
`/usr/share/fceux/palettes/FCEUX.pal`. Override them with `FCEUX` and
`FCEUX_PALETTE` when FCEUX is installed somewhere else. A missing palette
fails with that path named, before a native ROM is written.

```sh
make bootstrap
python3 -m pip install -r requirements-dev.txt
python3 tools/bootstrap_core.py
make verify
python3 tools/check_adapter.py --core .deps/snes9x/libretro/snes9x_libretro.so
```

The optional core bootstrap pins Snes9x and applies the checked-in debug patch.
It refuses unexpected revisions/modifications. This is not a stock-core claim:
receipts identify the exact shared library and harness hashes.

Place your validated original US ROM at `roms/river-city-ransom-us.nes`.
Each output directory below must be new; captures/builds refuse overwrite.

Named playable trials (4108, 4146, 4162, 4163) are not this generic native
image. Rebuild those with `make playable` as documented in the README. That
target needs local build 3955 or 3800, which are not produced by the two
captures below.

```sh
python3 tools/capture_nes.py --out build/reference-title --profile title --frames 600
python3 tools/capture_nes.py --out build/reference-walk --profile walk --frames 1800
python3 tools/build_native.py --trace build/reference-title --trace build/reference-walk --out build/native
python3 tools/smoke_libretro.py --core .deps/snes9x/libretro/snes9x_libretro.so \
  --rom build/native/native-cpu.sfc --kind native --profile walk --frames 12000 \
  --screenshot build/native/soak.png --ram build/native/soak.ram \
  --receipt build/native/soak-receipt.json
python3 tools/audit.py --capture build/reference-title \
  --core .deps/snes9x/libretro/snes9x_libretro.so --out build/renderer-audit
python3 tools/live_audit.py --candidate build/native --title build/reference-title \
  --walk build/reference-walk --core .deps/snes9x/libretro/snes9x_libretro.so \
  --out build/live-audit
```

Run emulator captures serially. FCEUX owns an isolated process group and lock;
timeouts terminate only that group, not other emulator instances. Libretro runs
must use separate processes, as the core is process-global. `--kind render`
checks video callbacks only; `--kind native` checks advancing NMI counters and
adapter faults; neither substitutes for image/input/audio equivalence tests.
`--kind adapter` verifies the asset-free native runtime test cartridge. Its
negative control corrupts a separate synthetic CHR byte and requires the precise
CPU assertion failure, not just an arbitrary emulator process error.

## Review in a browser

Only generated `site/` directories contain publication-safe media/HTML/JSON.
They omit ROMs, VRAM/RAM snapshots and raw extracted assets. Open `index.html`
locally, or serve **only** a site directory on loopback:

```sh
python3 -m http.server 8765 --bind 127.0.0.1 --directory build/live-audit/site
```

Open `http://127.0.0.1:8765`. Reviews save in browser local storage under exact
evidence hashes; export JSON to share them. A new candidate/evidence hash starts
unreviewed. Static collages also render directly in the private GitHub repo.
Public GitHub Pages deployment remains disabled pending explicit visibility approval.
