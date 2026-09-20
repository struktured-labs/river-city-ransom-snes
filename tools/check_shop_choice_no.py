"""NES oracle for visible YES/NO cursor traversal and NO confirmation."""
import argparse
import html
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image

try:
    from .benchmark_report import sha, verify_capture
    from .check_shop_confirm import GLYPHS, REGION
except ImportError:
    from benchmark_report import sha, verify_capture
    from check_shop_confirm import GLYPHS, REGION


CURSORS = (0x2CE, 0x2D8)
OFFSETS = (*GLYPHS, 0x2D8)
PHASES = (
    ('shop_confirm_idle_3', 'yes'), ('shop_choose_no', 'no'),
    ('shop_no_idle', 'no'), ('shop_choose_yes_again', 'yes'),
    ('shop_yes_idle', 'yes'), ('shop_choose_no_again', 'no'),
    ('shop_no_again_idle', 'no'), ('shop_confirm_no', 'clear'),
    ('shop_no_result', 'clear'),
)
DISPLAY = ('shop_confirm_idle_3', 'shop_no_idle', 'shop_yes_idle',
           'shop_no_again_idle', 'shop_no_result')
MONEY = (45, 37, 102, 48)


def _pixels(folder, phase, rectangle):
    pixels = np.asarray(Image.open(folder/f'{phase}.png').convert('RGB'))
    x0, y0, x1, y1 = rectangle
    return pixels[y0:y1, x0:x1] >> 3


def _glyphs(folder, phase, vram=False):
    contents = (folder/f'{phase}.{"vram" if vram else "nametable"}').read_bytes()
    return [contents[(0x2000+offset)*2 if vram else offset] for offset in OFFSETS]


def _check_capture(folder, system, original, scenario):
    receipt, rows = verify_capture(folder)
    if (receipt['system'] != system or not receipt['capture_complete']
            or receipt['scenario_name'] != 'traversal-shop-no'
            or receipt['scenario_sha256'] != scenario
            or receipt['templates']['menu']['source_rom'] != original
            or (system == 'nes' and receipt['rom_sha256'] != original)
            or any(row['fault'] or row['input_requested'] != row['input_delivered'] for row in rows)):
        raise ValueError(f'Unbound cursor replay: {folder}')
    segments = {segment['name']: segment for segment in receipt['segments']}
    for phase, _ in PHASES:
        if phase not in segments or 'nametable_snapshot' not in segments[phase]:
            raise ValueError(f'Missing bound CIRAM at {phase}: {folder}')
        if system == 'snes' and 'vram_snapshot' not in segments[phase]:
            raise ValueError(f'Missing bound VRAM at {phase}: {folder}')
    return receipt


def _analyze(original, candidate):
    rows = []
    for phase, state in PHASES:
        nes, snes, vram = _glyphs(original, phase), _glyphs(candidate, phase), _glyphs(candidate, phase, True)
        mismatch = int(np.any(_pixels(original, phase, REGION) != _pixels(candidate, phase, REGION), axis=2).sum())
        expected = ((187, 0) if state == 'yes' else
                    (0, 187) if state == 'no' else (0, 0))
        if tuple(nes[i] for i in (0, -1)) != expected:
            raise ValueError(f'Original NES failed {state} cursor at {phase}')
        rows.append(dict(phase=phase, selected=state, original_glyphs=nes,
                         candidate_shadow=snes, candidate_vram=vram,
                         mismatch_pixels=mismatch,
                         passed=nes == snes == vram and mismatch == 0))
    original_money = _pixels(original, PHASES[0][0], MONEY)
    if np.any(original_money != _pixels(original, PHASES[-1][0], MONEY)):
        raise ValueError('Original NES NO selection unexpectedly spent money')
    money_match = all(np.array_equal(original_money, _pixels(candidate, phase, MONEY))
                      for phase in (PHASES[0][0], PHASES[-1][0]))
    return dict(passed=all(row['passed'] for row in rows) and money_match,
                unchanged_money_pixels=money_match, phases=rows)


def build(reference, previous, candidate, out):
    if out.exists():
        raise ValueError('Output directory already exists')
    ref = json.loads((reference/'capture.json').read_text())
    original, scenario = ref['rom_sha256'], ref['scenario_sha256']
    receipts = {label: _check_capture(folder, system, original, scenario)
                for label, folder, system in (('nes', reference, 'nes'),
                                              ('previous', previous, 'snes'),
                                              ('snes', candidate, 'snes'))}
    result = _analyze(reference, candidate)
    negative = _analyze(reference, previous)
    gates = dict(cursor_cycles_and_no_exact=result['passed'],
                 previous_stale_cursor_reproduced=(not negative['passed']
                    and negative['phases'][2]['mismatch_pixels'] >= 20
                    and negative['phases'][6]['mismatch_pixels'] >= 20))
    out.mkdir(parents=True)
    for label, folder in (('nes', reference), ('previous', previous), ('snes', candidate)):
        for phase in DISPLAY:
            shutil.copyfile(folder/f'{phase}.png', out/f'{label}-{phase}.png')
    report = dict(schema='rcr-shop-choice-no-audit-v1', passed=all(gates.values()),
                  gates=gates, scenario_sha256=scenario, source_rom_sha256=original,
                  fixed_region=REGION, cursor_offsets=[hex(i) for i in CURSORS],
                  captures={label: dict(path=str(folder), capture_sha256=sha(folder/'capture.json'),
                                        rom_sha256=receipts[label]['rom_sha256'])
                            for label, folder in (('nes', reference), ('previous', previous), ('snes', candidate))},
                  result=result, negative_control=negative,
                  scope='Fixed prompt pixels, original NES CIRAM, SNES shadow+actual VRAM, NO money. Does not certify other shops or physical audio.')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    cards = ''.join(f'<section><h2>{html.escape(phase)}</h2>'+
                    ''.join(f'<figure><figcaption>{label}</figcaption>'
                            f'<img src="{label}-{phase}.png"></figure>'
                            for label in ('nes', 'previous', 'snes'))+'</section>'
                    for phase in DISPLAY)
    (out/'index.html').write_text(
        '<!doctype html><meta charset="utf-8"><title>RCR shop NO cursor audit</title>'
        '<style>body{background:#101924;color:#f0f6ff;font:16px system-ui;padding:24px}'
        'section{border-top:1px solid #465;padding:12px 0}figure{display:inline-block;margin:8px}'
        'img{width:384px;image-rendering:pixelated}a{color:#54ddff}</style>'
        f'<h1>YES → NO → YES → NO → confirm NO: {"PASS" if report["passed"] else "FAIL"}</h1>'
        '<p>Original NES / stale-cursor SNES / corrected SNES; nine exact checkpoints and '
        'unchanged money after NO.</p>'+cards+
        '<p><a href="report.json">Hash-bound machine audit</a></p>')
    print(json.dumps(dict(passed=report['passed'], gates=gates,
                          phases=[(r['phase'], r['mismatch_pixels']) for r in result['phases']]), indent=2))
    return report['passed']


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('reference', 'previous', 'candidate', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    args = p.parse_args()
    raise SystemExit(0 if build(args.reference, args.previous, args.candidate, args.out) else 1)
