"""Build an optional pre-boot splash from the user's supplied branding assets.

No artwork generation: deterministic crop, resample, palette quantization, and
SNES planar encoding. Original game/menu bytes are preserved except reset jump.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys

import numpy as np
from PIL import Image, __version__ as pillow_version

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA = 'b95f8def04c0012604b7cc68cf4ed8f49b2dfe4beda6182051de4b2423bea7b1'
LOGO_CROP = (160, 128, 864, 832)
WORD_CROP = (820, 264, 1780, 361)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def artwork(logo, wordmark, ruler=False):
    if logo.size != (1024, 1024) or wordmark.size != (1983, 793):
        raise ValueError('Unexpected branding source geometry; review crop before continuing')
    canvas = Image.new('RGB', (256, 239))
    canvas.paste(logo.convert('RGB').crop(LOGO_CROP).resize((184, 184), Image.Resampling.LANCZOS), (36, 8))
    word = np.asarray(wordmark.convert('RGB').crop(WORD_CROP))
    # White text only: minimum channel rejects cyan/purple background graphics.
    light = word.min(axis=2).copy()
    light[light < 40] = 0
    word = Image.fromarray(light).convert('RGB').resize((224, 23), Image.Resampling.LANCZOS)
    canvas.paste(word, (16, 204))
    if ruler:
        canvas.paste((255, 255, 255), (0, 232, 256, 233))
    return canvas


def encode(canvas):
    # Reduce to native RGB555 before palette selection. Reserve index zero black.
    rgb5 = np.asarray(canvas).astype(np.uint16) >> 3
    reduced = Image.fromarray((rgb5 * 255 // 31).astype(np.uint8))
    quant = reduced.quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    source_palette = np.array(quant.getpalette(), dtype=np.uint8).reshape(-1, 3) >> 3
    palette5 = np.zeros((256, 3), dtype=np.uint8)
    palette5[1:len(source_palette) + 1] = source_palette
    indexes = np.asarray(quant).astype(np.uint16) + 1
    indexes[np.all(palette5[indexes] == 0, axis=2)] = 0
    palette = bytearray()
    for r, g, b in palette5:
        palette += struct.pack('<H', int(r) | int(g) << 5 | int(b) << 10)
    frame = np.zeros((256, 256), dtype=np.uint8)
    frame[:239] = indexes
    unique, tileids, tiles = {}, [], bytearray()
    for ty in range(32):
        for tx in range(32):
            pixels = frame[ty*8:ty*8+8, tx*8:tx*8+8]
            key = pixels.tobytes()
            if key not in unique:
                unique[key] = len(unique)
                for plane in range(0, 8, 2):
                    for y in range(8):
                        for bit in (plane, plane + 1):
                            tiles.append(sum(((int(pixels[y, x]) >> bit) & 1) << (7-x) for x in range(8)))
            tileids.append(unique[key])
    if len(tiles) > 0xE000 or len(unique) > 1024:
        raise ValueError('Splash tiles exceed bank/VRAM budget')
    tilemap = struct.pack('<1024H', *tileids)
    preview = Image.fromarray((palette5[indexes].astype(np.uint16) * 255 // 31).astype(np.uint8))
    return bytes(tiles), tilemap, bytes(palette), preview


def patch(image, splash):
    if len(image) != 0x200000 or len(splash) != 0x10000:
        raise ValueError('Expected 2 MiB native image and 64 KiB splash bank')
    if image[0x8000:0x8005] != bytes.fromhex('7818fbc238'):
        raise ValueError('Native reset preimage mismatch')
    if image[0x110000:0x120000] != b'\xff' * 0x10000:
        raise ValueError('D1 bank is occupied; do not overwrite')
    complement, checksum = struct.unpack_from('<HH', image, 0xFFDC)
    if complement ^ checksum != 0xFFFF or sum(image) & 0xFFFF != checksum:
        raise ValueError('Native checksum mismatch')
    result = bytearray(image)
    result[0x8000:0x8005] = bytes.fromhex('5c0000d1ea')
    result[0x110000:0x120000] = splash
    result[0xFFDC:0xFFE0] = b'\xff\xff\0\0'
    checksum = sum(result) & 0xFFFF
    struct.pack_into('<HH', result, 0xFFDC, checksum ^ 0xFFFF, checksum)
    return bytes(result)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--logo', type=Path, required=True)
    p.add_argument('--wordmark-reference', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--diagnostic-ruler', action='store_true')
    p.add_argument('--wrong-step', action='store_true', help='Negative-control build')
    p.add_argument('--dirty-vram', action='store_true', help='Negative-control teardown build')
    p.add_argument('--dirty-window', action='store_true', help='Negative-control window teardown build')
    p.add_argument('--ident-audio', action='store_true', help='Experimental original SPC ident and four-second hold')
    p.add_argument('--ident-dry-control', action='store_true', help='Negative control with echo disabled; requires --ident-audio')
    args = p.parse_args()
    if args.ident_dry_control and not args.ident_audio:
        p.error('--ident-dry-control requires --ident-audio')
    data = (args.candidate / 'native-cpu.sfc').read_bytes()
    manifest = json.loads((args.candidate / 'manifest.json').read_text())
    if manifest['rom_sha256'] != sha(data) or manifest['source_rom_sha256'] != SOURCE_SHA:
        raise ValueError('Unbound native candidate')
    args.out.mkdir(parents=True, exist_ok=False)
    canvas = artwork(Image.open(args.logo), Image.open(args.wordmark_reference), args.diagnostic_ruler)
    tiles, tilemap, palette, preview = encode(canvas)
    for name, payload in [('tiles', tiles), ('map', tilemap), ('palette', palette)]:
        (args.out / f'splash-{name}.bin').write_bytes(payload)
    canvas.save(args.out / 'resampled.png')
    preview.save(args.out / 'preview.png')
    shutil.copyfile(args.logo, args.out / 'source-logo.png')
    shutil.copyfile(args.wordmark_reference, args.out / 'source-wordmark-reference.png')
    defines = ['-D', 'WRONG_STEP=1'] if args.wrong_step else []
    if args.dirty_vram:
        defines += ['-D', 'DIRTY_VRAM=1']
    if args.diagnostic_ruler:
        defines += ['-D', 'DIAGNOSTIC_RULER=1']
    if args.dirty_window:
        defines += ['-D', 'DIRTY_WINDOW=1']
    if args.ident_audio:
        subprocess.run([sys.executable, str(ROOT / 'tools/build_ident_spc.py'),
                        '--out', str(args.out / 'splash-ident-spc.bin'),
                        '--curve', str(args.out / 'splash-ident-curve.bin'),
                        *(['--dry-control'] if args.ident_dry_control else [])], check=True)
        defines += ['-D', 'IDENT_AUDIO=1']
    subprocess.run([str(ROOT / '.deps/cc65/bin/ca65'), *defines, '--bin-include-dir', str(args.out),
                    '-o', str(args.out / 'splash.o'), str(ROOT / 'snes/branding_splash.asm')], check=True)
    subprocess.run([str(ROOT / '.deps/cc65/bin/ld65'), '-C', str(ROOT / 'snes/branding_splash.cfg'),
                    '-Ln', str(args.out / 'splash.lbl'), '-o', str(args.out / 'splash.bin'),
                    str(args.out / 'splash.o')], check=True)
    branded = patch(data, (args.out / 'splash.bin').read_bytes())
    (args.out / 'native-cpu.sfc').write_bytes(branded)
    manifest.update(rom_sha256=sha(branded), splash={
        'parent_rom_sha256': sha(data), 'logo_sha256': sha(args.logo.read_bytes()),
        'wordmark_reference_sha256': sha(args.wordmark_reference.read_bytes()),
        'logo_crop': LOGO_CROP, 'wordmark_crop': WORD_CROP, 'logo_size': [184, 184],
        'wordmark_size': [224, 23], 'tile_count': len(tiles)//64,
        'diagnostic_ruler': args.diagnostic_ruler, 'wrong_step': args.wrong_step,
        'dirty_vram': args.dirty_vram,
        'dirty_window': args.dirty_window,
        'ident_audio': args.ident_audio,
        'ident_dry_control': args.ident_dry_control,
        'ident_curve_sha256': sha((args.out / 'splash-ident-curve.bin').read_bytes()) if args.ident_audio else None,
        'hold_frames': 240 if args.ident_audio else 180,
        'ident_spc_sha256': sha((args.out / 'splash-ident-spc.bin').read_bytes()) if args.ident_audio else None,
        'palette_used': len(np.unique(np.asarray(preview).reshape(-1, 3), axis=0)),
        'converter_sha256': sha(Path(__file__).read_bytes()),
        'assembly_sha256': sha((ROOT / 'snes/branding_splash.asm').read_bytes()),
        'linker_config_sha256': sha((ROOT / 'snes/branding_splash.cfg').read_bytes()),
        'pillow_version': pillow_version, 'numpy_version': np.__version__,
        'scope': 'Optional user-logo preboot splash; original art/menu unchanged'} )
    (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest['splash'], indent=2))


if __name__ == '__main__':
    main()
