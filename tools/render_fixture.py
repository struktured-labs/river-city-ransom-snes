"""Build a native SNES renderer fixture from an authenticated NES capture."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess

try:
    from .checksum import finalize
    from .fceux_env import require_palette
    from .rom import convert_chr
except ImportError:
    from checksum import finalize
    from fceux_env import require_palette
    from rom import convert_chr

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assets(ppu, nes_oam, ctrl, rgb):
    if len(ppu) != 16384 or len(nes_oam) != 256 or len(rgb) < 192:
        raise ValueError("Incomplete NES PPU/OAM/palette snapshot")
    bg = convert_chr(ppu[:8192])
    obj = convert_chr(ppu[:8192], 4)
    base = 0x2000 + (ctrl & 3) * 1024
    tilemap = bytearray(2048)
    for y in range(30):
        for x in range(32):
            attr = ppu[base + 960 + (y // 4) * 8 + x // 4]
            palette = (attr >> (((y & 2) << 1) | (x & 2))) & 3
            tile = ppu[base + y * 32 + x] + (256 if ctrl & 0x10 else 0)
            struct.pack_into("<H", tilemap, (y * 32 + x) * 2, tile | palette << 10)
    palette_data = bytearray(512)
    def color(index):
        # Mirror universal background entries, independent of dump representation.
        offset = 0 if index % 4 == 0 else index
        n = (ppu[0x3f00 + offset] & 63) * 3
        r, g, b = rgb[n:n + 3]
        return (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)
    for i in range(16):
        struct.pack_into("<H", palette_data, i * 2, color(i))
    for pal in range(4):
        for pixel in range(4):
            struct.pack_into("<H", palette_data, (128 + pal * 16 + pixel) * 2,
                             color(16 + pal * 4 + pixel))
    oam = bytearray(544)
    for i in range(128):
        oam[i * 4 + 1] = 240
    slot = 0
    for i in range(64):
        y, tile, attr, x = nes_oam[i * 4:i * 4 + 4]
        if y >= 239:
            continue
        tall = bool(ctrl & 0x20)
        parts = 2 if tall else 1
        for part in range(parts):
            if tall:
                index = (tile & 1) * 256 + (tile & 0xfe) + (1 - part if attr & 0x80 else part)
            else:
                index = tile + (256 if ctrl & 8 else 0)
            flags = (attr & 0xc0) | (0 if attr & 0x20 else 0x30) | ((attr & 3) << 1) | (index >> 8)
            # SNES emits its first visible scanline at line 1; compensate so
            # NES Y+1 lands on the same row in the captured framebuffer.
            oam[slot * 4:slot * 4 + 4] = bytes((x, (y + 2 + part * 8) & 255, index & 255, flags))
            slot += 1
    return {"bg.bin": bg, "obj.bin": obj, "tilemap.bin": tilemap,
            "palette.bin": palette_data, "oam.bin": oam}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--frame", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    prefix = f"frame-{args.frame:05d}"
    manifest = json.loads((args.capture / "manifest.json").read_text())
    for suffix in (".json", ".ppu", ".oam", ".png"):
        path = args.capture / (prefix + suffix)
        if digest(path) != manifest["files"][path.name]:
            raise ValueError(f"Capture file changed: {path.name}")
    palette = require_palette()
    if digest(palette) != manifest["palette_sha256"]:
        raise ValueError("Palette differs from reference capture")
    state = json.loads((args.capture / (prefix + ".json")).read_text())
    data = assets((args.capture / (prefix + ".ppu")).read_bytes(),
                  (args.capture / (prefix + ".oam")).read_bytes(), state["ppu_ctrl"], palette.read_bytes())
    args.out.mkdir(parents=True, exist_ok=False)
    for name, value in data.items():
        (args.out / name).write_bytes(value)
    (args.out / "snapshot.inc").write_text("SNAP_SCROLL_X = 0\nSNAP_SCROLL_Y = $FFFF\n")
    subprocess.run([str(ROOT / ".deps/cc65/bin/ca65"), "-I", str(args.out), "--bin-include-dir", str(args.out),
                    "-o", str(args.out / "render.o"), str(ROOT / "snes/render.asm")], check=True)
    output = args.out / "render.sfc"
    subprocess.run([str(ROOT / ".deps/cc65/bin/ld65"), "-C", str(ROOT / "snes/render.cfg"),
                    "-o", str(output), str(args.out / "render.o")], check=True)
    output.write_bytes(finalize(output.read_bytes()))
    (args.out / "manifest.json").write_text(json.dumps({
        "schema": "rcr-render-fixture-v1", "kind": "static-renderer-fixture-not-gameplay",
        "rom_sha256": digest(output), "source_rom_sha256": manifest["rom_sha256"],
        "capture_manifest_sha256": digest(args.capture / "manifest.json"),
        "reference_image_sha256": manifest["files"][prefix + ".png"],
        "source_frame": args.frame, "source_capture": str(args.capture.resolve()),
        "renderer_sha256": digest(ROOT / "snes/render.asm"),
    }, indent=2) + "\n")
    print(output)


if __name__ == "__main__":
    main()
