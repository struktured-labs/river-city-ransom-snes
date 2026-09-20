"""Explicit camera-matched checkpoint audit; differences are never aligned away."""
import argparse
import json
from pathlib import Path
import shutil
import numpy as np
from PIL import Image

try:
    from .benchmark_report import verify_capture, sha
    from .audit import compare
except ImportError:
    from benchmark_report import verify_capture, sha
    from audit import compare


def camera_key(ram):
    if len(ram) < 2048:
        raise ValueError('Missing original game RAM')
    return (int.from_bytes(ram[0xDC:0xDE], 'little'), ram[0xF6] | ((ram[0x3D] & 1) << 8))


def require_same_camera(reference, candidate):
    a, b = camera_key(reference), camera_key(candidate)
    if reference[0x42] != candidate[0x42]:
        raise ValueError('Original room identifiers differ')
    if a != b:
        raise ValueError(f'Camera position mismatch: {a} versus {b}')
    return a


def build(reference, candidate, pairs, out):
    evidence = [verify_capture(p) for p in (reference, candidate)]
    for system, (receipt, rows) in zip(('nes', 'snes'), evidence):
        if (receipt['system'] != system or not receipt['capture_complete']
                or not receipt['scenario_name'].startswith('traversal')
                or any(r['fault'] for r in rows)
                or any(r['input_requested'] != r['input_delivered'] for r in rows)):
            raise ValueError('Need complete fault-free traversal captures')
    if evidence[0][0]['scenario_name'] != evidence[1][0]['scenario_name']:
        raise ValueError('Traversal input scenarios differ')
    if evidence[0][0]['rom_sha256'] != evidence[0][0]['templates']['menu']['source_rom']:
        raise ValueError('Wrong original reference ROM')
    if not pairs:
        raise ValueError('Explicit checkpoint pairs required')
    selected = []
    for pair in pairs:
        names = pair.split(':')
        if len(names) != 2:
            raise ValueError('Pair must be NES-phase:SNES-phase')
        ram = []
        for name, directory, (receipt, rows) in zip(names, (reference, candidate), evidence):
            if name not in {s['name'] for s in receipt['segments']}:
                raise ValueError('Unknown checkpoint')
            raw = (directory/f'{name}.ram').read_bytes()
            last = next(r for r in reversed(rows) if r['phase'] == name)
            if raw[:2048].hex() != last['game_ram_hex']:
                raise ValueError('Checkpoint RAM differs from verified frame evidence')
            ram.append(raw)
        selected.append((names, require_same_camera(*ram), ram[0][0x42]))
    out.mkdir(parents=True, exist_ok=False)
    report = dict(schema='rcr-camera-checkpoint-audit-v1', release_ready=False,
                  scope='Explicit equal-camera samples, not equal game time or independently verified room identity; actors are not masked',
                  region=[0, 32, 256, 112], pairs=[],
                  capture_hashes=[sha(p/'capture.json') for p in (reference, candidate)])
    html = ['<!doctype html><meta charset="utf-8"><title>Camera checkpoint audit</title>',
            '<style>body{background:#121923;color:white;font:16px system-ui;padding:24px}section{display:flex;gap:20px;flex-wrap:wrap}img{width:512px;max-width:100%;image-rendering:pixelated}</style>',
            '<h1>Camera-matched diagnostic checkpoints</h1>',
            '<p>Not a release or full scrolling verdict. Checkpoints are explicit, not image-search matches. ',
            'Equal camera registers do not prove equal rooms. Actors entering the fixed strip remain differences.</p>']
    for index, (names, key, room) in enumerate(selected):
        _, heat = compare(reference/f'{names[0]}.png', candidate/f'{names[1]}.png')
        strip = heat.crop(tuple(report['region']))
        mismatches = int(np.any(np.asarray(strip) != 0, axis=2).sum())
        report['pairs'].append(dict(reference=names[0], candidate=names[1],
                                    camera_x=key[0], scroll_x=key[1], room_id=room, pixels_compared=20480,
                                    mismatch_pixels=mismatches))
        html.append(f'<h2>{names[0]} / {names[1]}: camera {key[0]}, scroll {key[1]}</h2>'
                    f'<p>{mismatches} differing pixels in fixed strip.</p><section>')
        for system, directory, name in zip(('nes', 'snes'), (reference, candidate), names):
            filename = f'{index}-{system}.png'
            shutil.copyfile(directory/f'{name}.png', out/filename)
            html.append(f'<div><h3>{system}</h3><img src="{filename}" alt="{system} checkpoint"></div>')
        strip.save(out/f'{index}-difference.png')
        html.append(f'<div><h3>Strip differences</h3><img src="{index}-difference.png" alt="Unmasked pixel differences"></div></section>')
    report['exact_match'] = all(p['mismatch_pixels'] == 0 for p in report['pairs'])
    (out/'index.html').write_text('\n'.join(html))
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    (out/'bundle.json').write_text(json.dumps({'files': {p.name: sha(p) for p in sorted(out.iterdir())}}, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('reference', 'candidate', 'out'):
        parser.add_argument('--'+arg, type=Path, required=True)
    parser.add_argument('--pair', action='append', required=True)
    parser.add_argument('--require-match', action='store_true', help='Fail after preserving the audit if any requested strip differs')
    args = parser.parse_args()
    report = build(args.reference, args.candidate, args.pair, args.out)
    print(json.dumps(report, indent=2))
    raise SystemExit(1 if args.require_match and not report['exact_match'] else 0)
