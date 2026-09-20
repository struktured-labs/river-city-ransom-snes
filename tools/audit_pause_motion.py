"""Compare every pause-close animation frame at the same input-relative time."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image

try:
    from .benchmark_report import verify_capture, sha
    from .check_pause_cursor import REGION
except ImportError:
    from benchmark_report import verify_capture, sha
    from check_pause_cursor import REGION


def runs(samples):
    result = []
    for i, sample in enumerate(samples):
        if not result or result[-1]['pixels_sha256'] != sample['pixels_sha256']:
            result.append(dict(offset=i, frame=sample['frame'], pixels_sha256=sample['pixels_sha256']))
    return result


def capture(folder, system):
    receipt, rows = verify_capture(folder)
    if (receipt['system'] != system or not receipt['capture_complete']
            or receipt['scenario_name'] != 'pause-cursor-return' or not receipt['frame_images']
            or not receipt['full_ram_telemetry']
            or any(r['fault'] or r['input_requested'] != r['input_delivered'] for r in rows)):
        raise ValueError('Need a complete ordinary-input, full-RAM pause animation capture')
    selected = [r for r in rows if r['phase'] in ('pause_close', 'game_after_pause')]
    if not selected or selected[0]['phase'] != 'pause_close':
        raise ValueError('No pause closing interval')
    x0, y0, x1, y1 = REGION
    samples = []
    for r in selected:
        path = folder/r['frame_image']
        if sha(path) != r['frame_image_sha256']:
            raise ValueError('Per-frame screenshot changed')
        pixels = np.asarray(Image.open(path).convert('RGB'))[y0:y1,x0:x1] >> 3
        samples.append(dict(frame=r['frame'], image=r['frame_image'],
                            pixels_sha256=hashlib.sha256(pixels.tobytes()).hexdigest(),
                            blank=not np.any(pixels), pause=bytes.fromhex(r['game_ram_hex'])[0x3f]))
    if not samples[-1]['blank']:
        raise ValueError('Closing animation did not finish with the menu area cleared')
    return receipt, samples


def build(reference, parent, candidate, out):
    data = {label: capture(folder, system) for label, folder, system in
            (('nes',reference,'nes'), ('parent',parent,'snes'), ('candidate',candidate,'snes'))}
    original, expected = data['nes']
    if (any(r['scenario_sha256'] != original['scenario_sha256'] or
            r['templates']['menu']['source_rom'] != original['rom_sha256'] for r,s in data.values())
            or any(len(s) != len(expected) for r,s in data.values())):
        raise ValueError('Pause motion input/reference mismatch')
    comparisons = {}
    for label in ('parent','candidate'):
        samples = data[label][1]
        comparisons[label] = dict(
            unequal_offsets=[i for i,(a,b) in enumerate(zip(expected,samples))
                             if a['pixels_sha256'] != b['pixels_sha256']],
            steps=runs(samples),
            first_permanently_blank_offset=1+max(i for i,s in enumerate(samples) if not s['blank']))
    report = dict(comparisons=comparisons, original_steps=runs(expected),
        original_first_permanently_blank_offset=1+max(i for i,s in enumerate(expected) if not s['blank']),
        region=list(REGION), frames=len(expected),
        strict_frame_match=not comparisons['candidate']['unequal_offsets'],
        sources={label:dict(capture_sha256=sha(folder/'capture.json'), rom_sha256=data[label][0]['rom_sha256'])
                 for label,folder in (('nes',reference),('parent',parent),('candidate',candidate))},
        audit_sha256=sha(Path(__file__)),
        scope='Same input-relative frame offsets; no image shifting, search, or timing realignment. '
              'Different animation positions fail the strict check. This diagnoses closing motion, '
              'not gameplay speed or audio fidelity.')
    out.mkdir(parents=True,exist_ok=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    cards=[]
    # Explicit fixed offsets, not best-match search. Include the old checkpoint.
    for offset in (1,2,3,4,5,11,49,50):
        cards.append(f'<h2>Input-relative frame {offset}</h2>')
        for label,folder in (('nes',reference),('parent',parent),('candidate',candidate)):
            filename=f'{label}-{offset}.png'
            shutil.copyfile(folder/data[label][1][offset]['image'],out/filename)
            cards.append(f'<figure><figcaption>{label}</figcaption><img src="{filename}"></figure>')
    (out/'index.html').write_text('''<!doctype html><meta charset="utf-8"><title>Pause closing motion</title>
<style>body{background:#111820;color:#eee;font:16px system-ui;margin:30px}figure{display:inline-block}
img{width:384px;image-rendering:pixelated}a{color:#9cf}</style><h1>Pause closing motion</h1><p>'''+
        html.escape(report['scope'])+'</p><p><a href="report.json">Frame hashes and source binding</a></p>'+''.join(cards))
    print(json.dumps(dict(strict_frame_match=report['strict_frame_match'],
        blank_offsets={label: c['first_permanently_blank_offset'] for label,c in comparisons.items()},
        original_blank_offset=report['original_first_permanently_blank_offset']),indent=2))
    return report['strict_frame_match']


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('reference','parent','candidate','out'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    raise SystemExit(0 if build(a.reference,a.parent,a.candidate,a.out) else 1)
