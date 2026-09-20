"""Compare two purchases in one shop against untouched NES CIRAM and pixels."""
import argparse
import html
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image

try:
    from .benchmark_report import verify_capture, sha
    from .check_shop_confirm import GLYPHS, REGION
except ImportError:
    from benchmark_report import verify_capture, sha
    from check_shop_confirm import GLYPHS, REGION


PHASES = (
    'shop_confirm_idle_3', 'shop_accept_yes', 'shop_after_purchase_1',
    'shop_after_purchase_2', 'shop_after_purchase_3', 'shop_after_purchase_4',
    'shop_select_second', 'shop_second_confirm', 'shop_accept_second',
    'shop_after_purchase_5',
)
PROMPT_PHASES = ('shop_confirm_idle_3', 'shop_second_confirm')
DISPLAY_PHASES = ('shop_confirm_idle_3', 'shop_after_purchase_1',
                  'shop_second_confirm', 'shop_after_purchase_5')


def _check_capture(path, system, scenario_hash, source_hash):
    receipt, rows = verify_capture(path)
    if (receipt['system'] != system or not receipt['capture_complete']
            or receipt['scenario_name'] != 'traversal-shop-repeat'
            or receipt['scenario_sha256'] != scenario_hash
            or receipt['templates']['menu']['source_rom'] != source_hash
            or (system == 'nes' and receipt['rom_sha256'] != source_hash)
            or any(row['fault'] or row['input_requested'] != row['input_delivered'] for row in rows)):
        raise ValueError(f'Incomplete or unbound shop-repeat capture: {path}')
    segments = {item['name']: item for item in receipt['segments']}
    for phase in PHASES:
        if phase not in segments or 'nametable_snapshot' not in segments[phase]:
            raise ValueError(f'Missing bound nametable: {path}/{phase}')
        if system == 'snes' and 'vram_snapshot' not in segments[phase]:
            raise ValueError(f'Missing bound VRAM: {path}/{phase}')
    return receipt


def _glyphs(path, phase):
    data = (path/f'{phase}.nametable').read_bytes()
    return [data[index] for index in GLYPHS]


def _vram_glyphs(path, phase):
    data = (path/f'{phase}.vram').read_bytes()
    return [data[(0x2000+index)*2] for index in GLYPHS]


def _region(path, phase):
    pixels = np.asarray(Image.open(path/f'{phase}.png').convert('RGB'))
    x0, y0, x1, y1 = REGION
    return pixels[y0:y1, x0:x1] >> 3


def _analyze(reference, candidate):
    original_prompt = _glyphs(reference, PROMPT_PHASES[0])
    if (any(not glyph for glyph in original_prompt)
            or _glyphs(reference, PROMPT_PHASES[1]) != original_prompt
            or any(_glyphs(reference, phase) != [0]*len(GLYPHS)
                   for phase in PHASES if phase not in PROMPT_PHASES)):
        raise ValueError('NES replay did not confirm, clear, and reconfirm an item')
    measures = []
    for phase in PHASES:
        original = _glyphs(reference, phase)
        shadow = _glyphs(candidate, phase)
        vram = _vram_glyphs(candidate, phase)
        mismatch = int(np.any(_region(reference, phase) != _region(candidate, phase), axis=2).sum())
        measures.append(dict(phase=phase, original_glyphs=original,
                             candidate_shadow=shadow, candidate_vram=vram,
                             mismatch_pixels=mismatch,
                             passed=(shadow == original and vram == original and mismatch == 0)))
    return dict(passed=all(phase['passed'] for phase in measures), phases=measures)


def build(reference, candidate, previous, out):
    if out.exists():
        raise ValueError('Output directory already exists')
    source = json.loads((reference/'capture.json').read_text())
    original_hash, scenario_hash = source['rom_sha256'], source['scenario_sha256']
    receipts = {}
    for label, directory, system in (('nes', reference, 'nes'),
                                     ('snes', candidate, 'snes'),
                                     ('previous', previous, 'snes')):
        receipts[label] = _check_capture(directory, system, scenario_hash, original_hash)
    result = _analyze(reference, candidate)
    old = _analyze(reference, previous)
    gates = dict(two_purchases_exact=result['passed'],
                 previous_stuck_prompt_reproduced=(not old['passed']
                     and old['phases'][1]['mismatch_pixels'] >= 50
                     and old['phases'][-1]['mismatch_pixels'] >= 50))
    out.mkdir(parents=True)
    for label, directory in (('nes', reference), ('previous', previous), ('snes', candidate)):
        for phase in DISPLAY_PHASES:
            shutil.copyfile(directory/f'{phase}.png', out/f'{label}-{phase}.png')
    report = dict(schema='rcr-shop-repeat-audit-v1', passed=all(gates.values()),
                  gates=gates, phases=PHASES, region=REGION,
                  glyph_offsets=[hex(offset) for offset in GLYPHS],
                  scenario_sha256=scenario_hash, source_rom_sha256=original_hash,
                  captures={label: dict(path=str(directory),
                                        capture_sha256=sha(directory/'capture.json'),
                                        rom_sha256=receipt['rom_sha256'])
                            for label, directory, receipt in (
                                ('nes', reference, receipts['nes']),
                                ('previous', previous, receipts['previous']),
                                ('snes', candidate, receipts['snes']))},
                  candidate=result, negative_control=old,
                  scope='One café, two purchases without leaving: fixed original NES CIRAM, SNES shadow/VRAM, and unsearched fixed pixel region. Hardware audio not certified.')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    names = dict(shop_confirm_idle_3='First YES/NO prompt',
                 shop_after_purchase_1='After first purchase',
                 shop_second_confirm='Second YES/NO prompt',
                 shop_after_purchase_5='After second purchase')
    cards = ''.join('<section><h2>'+html.escape(names[phase])+'</h2>'+
                    ''.join(f'<figure><figcaption>{html.escape(label)}</figcaption>'
                            f'<img src="{label}-{phase}.png"></figure>'
                            for label in ('nes', 'previous', 'snes'))+'</section>'
                    for phase in DISPLAY_PHASES)
    (out/'index.html').write_text(
        '<!doctype html><meta charset="utf-8"><title>RCR repeat-purchase audit</title>'
        '<style>body{background:#101924;color:#f0f6ff;font:16px system-ui;padding:24px}'
        'section{border-top:1px solid #465;padding:12px 0}figure{display:inline-block;margin:8px}'
        'img{width:384px;image-rendering:pixelated}a{color:#54ddff}</style>'
        f'<h1>Two consecutive café purchases: {"PASS" if report["passed"] else "FAIL"}</h1>'
        '<p>Original NES / broken previous SNES / corrected SNES; every prompt pixel and'
        ' six glyphs checked in original CIRAM, SNES shadow, and SNES VRAM at ten phases.</p>'
        +cards+'<p><a href="report.json">Hash-bound machine audit</a></p>')
    print(json.dumps(dict(passed=report['passed'], gates=gates,
                          candidate_phases=result['phases'],
                          negative_phases=old['phases']), indent=2))
    return report['passed']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('reference', 'candidate', 'previous', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if build(args.reference, args.candidate, args.previous, args.out) else 1)
