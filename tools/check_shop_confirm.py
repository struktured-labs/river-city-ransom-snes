"""Hash-bound, fixed-coordinate original-NES shop YES/NO regression audit."""
import argparse
import html
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image

try:
    from .benchmark_report import verify_capture, sha
except ImportError:
    from benchmark_report import verify_capture, sha


GLYPHS = (0x2CE, 0x2CF, 0x2D0, 0x2D1, 0x2D9, 0x2DA)
REGION = (108, 170, 225, 188)
PHASES = ('shop_confirm_idle_1', 'shop_confirm_idle_2', 'shop_confirm_idle_3')


def _check_capture(path, system, scenario_hash, source_hash):
    receipt, rows = verify_capture(path)
    if (receipt['system'] != system or not receipt['capture_complete']
            or receipt['scenario_name'] != 'traversal-shop-confirm'
            or receipt['scenario_sha256'] != scenario_hash
            or receipt['templates']['menu']['source_rom'] != source_hash
            or (system == 'nes' and receipt['rom_sha256'] != source_hash)
            or any(row['fault'] or row['input_requested'] != row['input_delivered'] for row in rows)):
        raise ValueError(f'Invalid complete shop-confirmation capture: {path}')
    for phase in PHASES:
        segment = next(item for item in receipt['segments'] if item['name'] == phase)
        if 'nametable_snapshot' not in segment:
            raise ValueError(f'Missing bound CIRAM/nametable snapshot: {path}/{phase}')
    return receipt


def _glyphs(path, phase):
    data = (path/f'{phase}.nametable').read_bytes()
    return [data[index] for index in GLYPHS]


def _region(path, phase):
    image = np.asarray(Image.open(path/f'{phase}.png').convert('RGB'))
    x0, y0, x1, y1 = REGION
    return image[y0:y1, x0:x1] >> 3


def _analyze(reference, candidate):
    measures = []
    for phase in PHASES:
        original, ported = _glyphs(reference, phase), _glyphs(candidate, phase)
        changed = int(np.any(_region(reference, phase) != _region(candidate, phase), axis=2).sum())
        measures.append(dict(phase=phase, original_glyphs=original,
                             candidate_glyphs=ported, mismatch_pixels=changed))
    # The text first arrives at the second idle checkpoint. Require the six
    # actual original glyph codes and persistence; blank/old prompt must fail.
    first_blank = measures[0]['original_glyphs'] == [0]*6
    original_glyphs = measures[1]['original_glyphs']
    if not first_blank or any(not x for x in original_glyphs) or measures[2]['original_glyphs'] != original_glyphs:
        raise ValueError('Original NES reference did not exercise the YES/NO prompt')
    exact = all(row['mismatch_pixels'] == 0 and row['candidate_glyphs'] == row['original_glyphs']
                for row in measures)
    # A shadow match alone is insufficient: the staged tiles must reach the
    # hardware VRAM tilemap, at the fixed tile addresses corresponding to x/y.
    vram = (candidate/'shop_confirm_idle_3.vram').read_bytes()
    actual_vram = [vram[(0x2000+offset)*2] for offset in GLYPHS]
    return dict(phases=measures, candidate_vram_glyphs=actual_vram,
                passed=exact and actual_vram == original_glyphs)


def build(reference, candidate, previous, out):
    if out.exists():
        raise ValueError('Output directory already exists')
    ref = json.loads((reference/'capture.json').read_text())
    original_hash = ref['rom_sha256']
    scenario_hash = ref['scenario_sha256']
    for directory, system in ((reference, 'nes'), (candidate, 'snes')):
        _check_capture(directory, system, scenario_hash, original_hash)
    result = _analyze(reference, candidate)
    if previous:
        _check_capture(previous, 'snes', scenario_hash, original_hash)
        prior = _analyze(reference, previous)
        if prior['passed'] or prior['phases'][-1]['mismatch_pixels'] < 50:
            raise ValueError('Negative control did not reproduce the missing prompt')
        result['negative_control'] = prior
    gates = dict(prompt_pixels_and_shadow_match=result['passed'],
                 regression_control_rejected=previous is not None and not result['negative_control']['passed'])
    out.mkdir(parents=True)
    for label, directory in (('nes', reference), ('snes', candidate), ('previous', previous)):
        if directory is not None:
            shutil.copyfile(directory/'shop_confirm_idle_3.png', out/f'{label}.png')
    report = dict(schema='rcr-shop-confirm-audit-v1', passed=all(gates.values()), gates=gates,
                  glyph_offsets=[hex(x) for x in GLYPHS], region=REGION,
                  scenario_sha256=scenario_hash,
                  source_rom_sha256=original_hash,
                  captures={label: dict(path=str(directory), capture_sha256=sha(directory/'capture.json'),
                                        rom_sha256=json.loads((directory/'capture.json').read_text())['rom_sha256'])
                            for label, directory in (('nes', reference), ('snes', candidate), ('previous', previous))
                            if directory is not None},
                  result=result,
                  scope='Café YES/NO after selecting an item; fixed pixels, original CIRAM and SNES shadow/VRAM. No other shops or hardware audio certified.')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    cards = ''.join(f'<figure><figcaption>{html.escape(label)}</figcaption><img src="{label}.png"></figure>'
                    for label in ('nes', 'previous', 'snes') if (out/f'{label}.png').exists())
    (out/'index.html').write_text(
        '<!doctype html><meta charset="utf-8"><title>RCR shop YES/NO audit</title>'
        '<style>body{background:#101924;color:#f0f6ff;font:16px system-ui;padding:24px}'
        'figure{display:inline-block;margin:10px}img{width:512px;image-rendering:pixelated}'
        'a{color:#54ddff}code{color:#97eeae}</style>'
        f'<h1>Café YES/NO: {"PASS" if report["passed"] else "FAIL"}</h1>'
        '<p>Original NES, deliberately broken previous SNES, corrected SNES. No scaling/alignment search.</p>'
        f'<p>Fixed rectangle {REGION}, RGB555. Original glyphs: <code>{result["phases"][-1]["original_glyphs"]}</code>; '
        f'new VRAM glyphs: <code>{result["candidate_vram_glyphs"]}</code>.</p>'
        +cards+'<p><a href="report.json">Machine-readable hash-bound audit</a></p>')
    print(json.dumps({'passed': report['passed'], 'gates': gates, 'result': result}, indent=2))
    return report['passed']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('reference', 'candidate', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--previous', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if build(args.reference, args.candidate, args.previous, args.out) else 1)
