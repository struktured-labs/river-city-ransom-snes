"""Verified Start/Select HUD and lower-menu comparison, not full-game fidelity."""
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

PHASES = ('idle', 'after_0_Start', 'after_1_Select', 'after_exit')
REGIONS = {'hud': (8, 8, 192, 24), 'menu': (8, 194, 256, 224)}


def evaluate(images):
    patches = {}
    for system, height in (('nes', 240), ('snes', 239)):
        for phase in PHASES:
            frame = np.asarray(images[system][phase])
            if frame.shape != (height, 256, 3) or frame.dtype != np.uint8:
                raise ValueError('Unexpected frame geometry or pixel type')
            for region, (x0, y0, x1, y1) in REGIONS.items():
                patches[system, phase, region] = frame[y0:y1, x0:x1] >> 3
    gates = []
    for phase in PHASES:
        for region in REGIONS:
            mismatch = np.any(patches['nes', phase, region] != patches['snes', phase, region], axis=2)
            gates.append(dict(gate=f'{phase}:{region}', passed=not bool(mismatch.any()),
                              mismatch_pixels=int(mismatch.sum())))
    for system in ('nes', 'snes'):
        for before, after, region in (('idle', 'after_0_Start', 'menu'),
                                      ('after_0_Start', 'after_1_Select', 'hud')):
            changed = int(np.any(patches[system, before, region] != patches[system, after, region], axis=2).sum())
            gates.append(dict(gate=f'{system}:{region}:transition', passed=changed > 0,
                              changed_pixels=changed))
    return gates


def build(reference, candidate, out):
    evidence = [verify_capture(p) for p in (reference, candidate)]
    for expected, (receipt, rows) in zip(('nes', 'snes'), evidence):
        if (receipt['system'] != expected or receipt['scenario_name'] != 'start-select'
                or not receipt['capture_complete'] or any(r['fault'] for r in rows)
                or any(r['input_requested'] != r['input_delivered'] for r in rows)):
            raise ValueError('Need complete, fault-free, input-verified Start/Select captures')
    if evidence[0][0]['rom_sha256'] != evidence[0][0]['templates']['menu']['source_rom']:
        raise ValueError('Wrong original reference ROM')
    images = {system: {p: np.array(Image.open(directory/f'{p}.png').convert('RGB')) for p in PHASES}
              for system, directory in (('nes', reference), ('snes', candidate))}
    gates = evaluate(images)
    report = dict(schema='rcr-menu-audit-v1', release_ready=False,
                  scope='Start/Select HUD and bottom menu only; not actors, scrolling, timing, audio, or physical hardware',
                  passed=all(g['passed'] for g in gates), gates=gates,
                  regions=REGIONS, pixel_comparison='RGB reduced to five bits per channel, fixed coordinates',
                  captures={s: sha(p/'capture.json') for s, p in (('nes', reference), ('snes', candidate))},
                  roms={s: e[0]['rom_sha256'] for s, e in zip(('nes', 'snes'), evidence)})
    out.mkdir(parents=True, exist_ok=False)
    html = ['<!doctype html><meta charset="utf-8"><title>RCR Start/Select audit</title>',
            '<style>body{background:#121923;color:white;font:16px system-ui;padding:24px}section{display:flex;gap:24px;flex-wrap:wrap}img{width:512px;image-rendering:pixelated;max-width:100%}</style>',
            f'<h1>Start/Select scoped check: {"PASS" if report["passed"] else "FAIL"}</h1>',
            '<p>Not release-ready. Fixed HUD/menu regions only; actors and street pixels are outside the gate. ',
            '“after_exit” is the existing scenario label for pressing B; it does not imply the menu closed.</p>']
    for phase in PHASES:
        html.append(f'<h2>{phase}</h2><section>')
        for system, directory in (('nes', reference), ('snes', candidate)):
            name = f'{system}-{phase}.png'
            shutil.copyfile(directory/f'{phase}.png', out/name)
            html.append(f'<div><h3>{system.upper()}</h3><img src="{name}" alt="{system} {phase}"></div>')
        html.append('</section>')
    for system, directory in (('nes', reference), ('snes', candidate)):
        shutil.copyfile(directory/'audio.wav', out/f'{system}-audio.wav')
        html.append(f'<h2>{system.upper()} complete recording (not audio-certified)</h2><audio controls src="{system}-audio.wav"></audio>')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    (out/'index.html').write_text('\n'.join(html))
    (out/'bundle.json').write_text(json.dumps({'schema': 'rcr-menu-bundle-v1',
        'files': {p.name: sha(p) for p in sorted(out.iterdir())}}, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('reference', 'candidate', 'out'):
        parser.add_argument('--'+arg, type=Path, required=True)
    args = parser.parse_args()
    report = build(args.reference, args.candidate, args.out)
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report['passed'] else 1)
