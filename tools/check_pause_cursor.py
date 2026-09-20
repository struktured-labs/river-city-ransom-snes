"""Hash-bound original-NES oracle for a stale menu cursor after pause reopen."""
import argparse
import html
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image

try:
    from .benchmark_report import sha, verify_capture
except ImportError:
    from benchmark_report import sha, verify_capture


HELP_CURSOR = 0x777
REGION = (8, 192, 250, 232)
PHASES = ('pause_visible', 'pause_right_visible_1', 'pause_right_visible_2',
          'pause_right_visible_3', 'pause_right_visible_4',
          'pause_cancel_visible', 'pause_close', 'game_after_pause',
          'pause_reopen_visible')
DISPLAY = ('pause_visible', 'pause_right_visible_4', 'pause_cancel_visible',
           'game_after_pause', 'pause_reopen_visible')


def _check_capture(folder, system, original_rom, scenario):
    receipt, frames = verify_capture(folder)
    if (receipt['system'] != system or not receipt['capture_complete']
            or receipt['scenario_name'] != 'pause-cursor-return'
            or receipt['scenario_sha256'] != scenario
            or receipt['templates']['menu']['source_rom'] != original_rom
            or (system == 'nes' and receipt['rom_sha256'] != original_rom)
            or any(row['fault'] or row['input_requested'] != row['input_delivered'] for row in frames)):
        raise ValueError(f'Unbound pause-selector replay: {folder}')
    segments = {segment['name']: segment for segment in receipt['segments']}
    for phase in PHASES:
        if phase not in segments or 'nametable_snapshot' not in segments[phase]:
            raise ValueError(f'Missing original CIRAM or shadow at {folder}/{phase}')
        if system == 'snes' and 'vram_snapshot' not in segments[phase]:
            raise ValueError(f'Missing SNES VRAM at {folder}/{phase}')
    return receipt


def _glyph(folder, phase, vram=False):
    data = (folder/f'{phase}.{"vram" if vram else "nametable"}').read_bytes()
    return data[(0x2000+HELP_CURSOR)*2 if vram else HELP_CURSOR]


def _pixels(folder, phase):
    pixels = np.asarray(Image.open(folder/f'{phase}.png').convert('RGB'))
    x0, y0, x1, y1 = REGION
    return pixels[y0:y1, x0:x1] >> 3


def _analyze(reference, candidate):
    if (_glyph(reference, 'pause_visible') != 0
            or _glyph(reference, 'pause_right_visible_4') != 187
            or any(_glyph(reference, phase) != 0
                   for phase in ('pause_close', 'game_after_pause', 'pause_reopen_visible'))):
        raise ValueError('Original NES replay did not create and clear HELP cursor')
    rows = []
    for phase in PHASES:
        original = _glyph(reference, phase)
        shadow, vram = _glyph(candidate, phase), _glyph(candidate, phase, True)
        mismatch = int(np.any(_pixels(reference, phase) != _pixels(candidate, phase), axis=2).sum())
        rows.append(dict(phase=phase, original=original, shadow=shadow, vram=vram,
                         mismatch_pixels=mismatch,
                         passed=original == shadow == vram and mismatch == 0))
    return dict(passed=all(row['passed'] for row in rows), phases=rows)


def build(reference, previous, candidate, out):
    if out.exists():
        raise ValueError('Output directory already exists')
    ref = json.loads((reference/'capture.json').read_text())
    source_rom, scenario = ref['rom_sha256'], ref['scenario_sha256']
    receipts = {label: _check_capture(folder, system, source_rom, scenario)
                for label, folder, system in (('nes', reference, 'nes'),
                                              ('previous', previous, 'snes'),
                                              ('snes', candidate, 'snes'))}
    result, negative = _analyze(reference, candidate), _analyze(reference, previous)
    gates = dict(selector_pixels_and_vram_match=result['passed'],
                 previous_lingering_cursor_rejected=(not negative['passed']
                     and negative['phases'][-1]['mismatch_pixels'] >= 16
                     and negative['phases'][-1]['shadow'] == 187))
    out.mkdir(parents=True)
    for label, folder in (('nes', reference), ('previous', previous), ('snes', candidate)):
        for phase in DISPLAY:
            shutil.copyfile(folder/f'{phase}.png', out/f'{label}-{phase}.png')
    report = dict(schema='rcr-pause-cursor-audit-v1', passed=all(gates.values()),
                  gates=gates, scenario_sha256=scenario, source_rom_sha256=source_rom,
                  help_cursor_offset=hex(HELP_CURSOR), region=REGION,
                  captures={label: dict(path=str(folder), capture_sha256=sha(folder/'capture.json'),
                                        rom_sha256=receipts[label]['rom_sha256'])
                            for label, folder in (('nes', reference), ('previous', previous), ('snes', candidate))},
                  result=result, negative_control=negative,
                  scope='Five selector labels, cancel, resume, reopen. Original NES CIRAM, SNES shadow/VRAM and fixed menu pixels. Physical audio not certified.')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    cards = ''.join(f'<section><h2>{html.escape(phase)}</h2>'+
                    ''.join(f'<figure><figcaption>{label}</figcaption>'
                            f'<img src="{label}-{phase}.png"></figure>'
                            for label in ('nes', 'previous', 'snes'))+'</section>'
                    for phase in DISPLAY)
    (out/'index.html').write_text(
        '<!doctype html><meta charset="utf-8"><title>RCR selector cursor audit</title>'
        '<style>body{background:#101924;color:#f0f6ff;font:16px system-ui;padding:24px}'
        'section{border-top:1px solid #465;padding:12px 0}figure{display:inline-block;margin:8px}'
        'img{width:384px;image-rendering:pixelated}a{color:#54ddff}</style>'
        f'<h1>Pause selector return: {"PASS" if report["passed"] else "FAIL"}</h1>'
        '<p>Original NES / old lingering-cursor SNES / corrected SNES. '
        'HELP must be unmarked after leaving and reopening the selector.</p>'+cards+
        '<p><a href="report.json">Hash-bound machine audit</a></p>')
    print(json.dumps(dict(passed=report['passed'], gates=gates, phases=[
        (row['phase'], row['mismatch_pixels']) for row in result['phases']]), indent=2))
    return report['passed']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('reference', 'previous', 'candidate', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if build(args.reference, args.previous, args.candidate, args.out) else 1)
