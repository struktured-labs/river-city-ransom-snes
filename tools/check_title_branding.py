"""Execute opt-in footer branding and audit exact glyphs, scope, and audio."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
from PIL import Image

try:
    from .brand_title import LABEL, SOURCE_SHA, encode, patch
except ImportError:
    from brand_title import LABEL, SOURCE_SHA, encode, patch

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def visual_gates(a, b, expected):
    if a.shape != (239, 256, 3) or b.shape != a.shape or expected.shape != (8, 232):
        raise ValueError('Unexpected framebuffer or glyph-oracle dimensions')
    changed = np.any(a != b, axis=2)
    outside = changed.copy()
    outside[200:208, 16:248] = False
    actual = np.min(b[200:208, 16:248], axis=2) >= 192
    return {'only_footer_pixels_changed': not bool(outside.any()),
            'footer_actually_changed': bool(changed.any()),
            'original_font_exact': bool(np.array_equal(expected, actual))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--branded', type=Path, required=True)
    parser.add_argument('--core', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    before = args.candidate / 'native-cpu.sfc'
    after = args.branded / 'native-cpu.sfc'
    if patch(before.read_bytes()) != after.read_bytes():
        raise ValueError('Branded cartridge differs from the exact scoped patch')
    reference = json.loads((args.reference / 'manifest.json').read_text())
    ppu = args.reference / 'frame-00600.ppu'
    if reference['rom_sha256'] != SOURCE_SHA or digest(ppu) != reference['files'][ppu.name]:
        raise ValueError('Original font snapshot is not authenticated')
    args.out.mkdir(parents=True, exist_ok=False)
    for label, rom in [('before', before), ('after', after)]:
        subprocess.run([sys.executable, str(ROOT / 'tools/smoke_libretro.py'),
                        '--core', str(args.core), '--rom', str(rom), '--frames', '600',
                        '--kind', 'native', '--screenshot', str(args.out / f'{label}.png'),
                        '--wav', str(args.out / f'{label}.wav'),
                        '--receipt', str(args.out / f'{label}.json')], check=True)
    a, b = [np.array(Image.open(args.out / f'{label}.png').convert('RGB')) for label in ('before', 'after')]
    changed = np.any(a != b, axis=2)
    # Independent pixel oracle: decode original NES CHR glyphs, not after.png.
    patterns = ppu.read_bytes()
    expected = np.zeros((8, 29 * 8), dtype=bool)
    for index, tile in enumerate(encode(LABEL)):
        for y in range(8):
            # Font background is color 2 (black), foreground color 3 (white).
            bits = patterns[tile * 16 + y] & patterns[tile * 16 + y + 8]
            for x in range(8):
                expected[y, index * 8 + x] = bool(bits & (128 >> x))
    gates = visual_gates(a, b, expected)
    gates['audio_byte_identical'] = digest(args.out / 'before.wav') == digest(args.out / 'after.wav')
    report = {'gates': gates, 'changed_pixels': int(changed.sum()),
              'parent_rom_sha256': digest(before), 'branded_rom_sha256': digest(after),
              'reference_ppu_sha256': digest(ppu), 'scope': '600-frame no-input boot/menu; not a gameplay or title-logo redesign verdict'}
    (args.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    (args.out / 'index.html').write_text('''<!doctype html><meta charset="utf-8"><title>SNES footer branding audit</title>
<style>body{background:#151b22;color:#eee;font:18px system-ui;max-width:1100px;margin:2em auto}img{width:512px;image-rendering:pixelated}figure{display:inline-block;margin:0 20px 20px 0}audio{display:block}</style>
<h1>SNES port branding — opt-in footer</h1><p>Original font, art, and Technos credits preserved. Replaces “Select game mode &amp; character.” on the 1P/2P menu; does not add a new logo.</p>
<figure><figcaption>Before</figcaption><img src="before.png"><audio controls src="before.wav"></audio></figure>
<figure><figcaption>After</figcaption><img src="after.png"><audio controls src="after.wav"></audio></figure>
<p><a href="report.json">Exact glyph / outside-region / audio checks</a>. Scope: 600-frame no-input boot/menu, not full gameplay certification.</p>''')
    print(json.dumps(report, indent=2))
    if not all(gates.values()):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
