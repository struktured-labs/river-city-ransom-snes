"""Audit the café menu at fixed coordinates against original NES gameplay."""
import argparse
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image

try:
    from .benchmark_report import verify_capture, sha
except ImportError:
    from benchmark_report import verify_capture, sha


REGION = (90, 56, 248, 166)


def menu_pixels(image):
    x0, y0, x1, y1 = REGION
    return np.asarray(image.convert('RGB'))[y0:y1, x0:x1] >> 3


def build(reference, candidate, out):
    evidence = [verify_capture(p) for p in (reference, candidate)]
    for system, (receipt, rows) in zip(('nes', 'snes'), evidence):
        if (receipt['system'] != system or not receipt['capture_complete']
                or receipt['scenario_name'] not in ('traversal-shop', 'traversal-shop-exit')
                or any(r['fault'] for r in rows)
                or any(r['input_requested'] != r['input_delivered'] for r in rows)):
            raise ValueError('Need complete fault-free shop route captures')
    if evidence[0][0]['rom_sha256'] != evidence[0][0]['templates']['menu']['source_rom']:
        raise ValueError('Wrong original reference ROM')
    # Room $42 stays 2 inside this shop: do not use room number as an arrival gate.
    expected_banks = [124, 126, 112, 113, 114, 115]
    reference_row = next(r for r in reversed(evidence[0][1]) if r['phase'] == 'observe_shop')
    if reference_row['nes_mapper']['registers'][:6] != expected_banks:
        raise ValueError('Original reference did not reach expected shop graphics')
    actual_row = next(r for r in reversed(evidence[1][1]) if r['phase'] == 'observe_shop')['native']
    images = [Image.open(p/'observe_shop.png') for p in (reference, candidate)]
    if [im.size for im in images] != [(256, 240), (256, 239)]:
        raise ValueError('Unexpected capture geometry')
    a, b = map(menu_pixels, images)
    if np.count_nonzero(np.all(a >= 24, axis=2)) < 100:
        raise ValueError('Reference lacks visible menu glyphs/border')
    mismatch = int(np.any(a != b, axis=2).sum())
    gates = dict(shop_chr_banks_match=actual_row['chr_registers'] == expected_banks,
                 chr_uploads_settled=actual_row['chr_jobs_pending'] == 0,
                 fixed_menu_pixels_match=mismatch == 0)
    report = dict(schema='rcr-shop-audit-v1', gates=gates, release_ready=False,
                  region=REGION, pixels_compared=a.shape[0]*a.shape[1],
                  mismatch_pixels=mismatch,
                  capture_sha256=[sha(p/'capture.json') for p in (reference, candidate)],
                  comparison='RGB555, fixed coordinates, no alignment search',
                  scope='First café menu only; actors/HUD and all other shops, audio and speed are not certified')
    out.mkdir(parents=True, exist_ok=False)
    html = ['<!doctype html><meta charset="utf-8"><title>Café menu audit</title>',
            '<style>body{background:#121923;color:white;font:16px system-ui;padding:24px}figure{display:inline-block}img{width:512px;image-rendering:pixelated}</style>',
            '<h1>Café menu regression</h1>',
            f'<p>{mismatch} differing pixels of {report["pixels_compared"]} in fixed rectangle {REGION}, RGB555.</p>',
            '<p>Complete frames below retain differences outside the menu. Not a full-game, speed or audio verdict.</p>']
    for system, folder in zip(('nes', 'snes'), (reference, candidate)):
        shutil.copyfile(folder/'observe_shop.png', out/f'{system}.png')
        html.append(f'<figure><figcaption>{system}</figcaption><img src="{system}.png"></figure>')
    html.append('<p><a href="report.json">Hash-bound result</a></p>')
    (out/'index.html').write_text('\n'.join(html))
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    return all(gates.values())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('reference', 'candidate', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if build(args.reference, args.candidate, args.out) else 1)
