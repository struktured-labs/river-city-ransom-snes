"""Bind a mall CHR-bank regression to verified NES/SNES traversal captures."""
import argparse
import json
from pathlib import Path
import shutil

try:
    from .benchmark_report import verify_capture, sha
except ImportError:
    from benchmark_report import verify_capture, sha


def checkpoint(rows, system):
    row = next(r for r in reversed(rows) if r['phase'] == 'observe_alley_exit')
    if bytes.fromhex(row['game_ram_hex'])[0x42] != 2:
        raise ValueError('Checkpoint did not reach mall room 2')
    if system == 'nes':
        return row['nes_mapper']['registers'][:6]
    if row['native']['chr_jobs_pending']:
        raise ValueError('Checkpoint still has unpublished CHR jobs')
    return row['native']['chr_registers']


def build(reference, candidate, out):
    captures = [verify_capture(p) for p in (reference, candidate)]
    banks = []
    accepted_scenarios = {'traversal-mall', 'traversal-shop', 'traversal-shop-exit'}
    for system, (receipt, rows) in zip(('nes', 'snes'), captures):
        if (receipt['system'] != system or not receipt['capture_complete']
                or receipt['scenario_name'] not in accepted_scenarios
                or any(r['fault'] for r in rows)
                or any(r['input_requested'] != r['input_delivered'] for r in rows)):
            raise ValueError('Need complete fault-free mall-prefix captures')
        banks.append(checkpoint(rows, system))
    if captures[0][0]['scenario_sha256'] != captures[1][0]['scenario_sha256']:
        raise ValueError('Input scenarios differ')
    if captures[0][0]['rom_sha256'] != captures[0][0]['templates']['menu']['source_rom']:
        raise ValueError('Wrong original reference ROM')
    passed = banks[0] == banks[1]
    out.mkdir(parents=True, exist_ok=False)
    report = dict(schema='rcr-mall-mapper-audit-v1', chr_registers=banks,
                  mall_chr_banks_match=passed, release_ready=False,
                  capture_sha256=[sha(p/'capture.json') for p in (reference, candidate)],
                  scope='Room-2 settled CHR bank selection; images are visual evidence, not actor-aligned pixel equivalence or speed/audio certification')
    html = ['<!doctype html><meta charset="utf-8"><title>Mall graphics-bank audit</title>',
            '<style>body{background:#121923;color:white;font:16px system-ui;padding:24px}figure{display:inline-block}img{width:512px;image-rendering:pixelated}</style>',
            '<h1>Mall graphics-bank regression</h1>',
            f'<p>CHR R0–R5 match: {passed}. NES {banks[0]}; SNES {banks[1]}.</p>',
            '<p>Same scripted route and room, not identical actor states. No image alignment or masking. Not a speed/audio verdict.</p>']
    for system, folder in zip(('nes', 'snes'), (reference, candidate)):
        shutil.copyfile(folder/'observe_alley_exit.png', out/f'{system}.png')
        html.append(f'<figure><figcaption>{system}</figcaption><img src="{system}.png"></figure>')
    html.append('<p><a href="report.json">Hash-bound report</a></p>')
    (out/'index.html').write_text('\n'.join(html))
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    return passed


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('reference', 'candidate', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if build(args.reference, args.candidate, args.out) else 1)
