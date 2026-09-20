"""Recheck previously proven renderer failures without shifting/selecting new frames."""
import argparse
import csv
import html
import json
from pathlib import Path
import shutil

from tools.audit_background_sweep import background_path, neutral
from tools.audit_render_scroll import bands, load_lines
from tools.benchmark_report import sha, verify_capture


def fixed_samples(old, current):
    selected = []
    if not old['comparisons']:
        raise ValueError('No previous failed samples')
    for before in old['comparisons']:
        now, = [r for r in current['comparisons'] if (r['room'], r['camera']) ==
                (before['room'], before['camera'])]
        if any(now[k] != before[k] for k in ('nes_frame', 'snes_frame')):
            raise ValueError('Previously fixed sample frame changed')
        selected.append((before, now))
    return selected


def audit(previous, sweep, background, renderer, normal, spans, out):
    if out.exists():
        raise ValueError('Use fresh output directory')
    old = json.loads((previous / 'report.json').read_text())
    for source, digest in old['sources'].items():
        if sha(Path(source)) != digest:
            raise ValueError('Previous renderer proof source changed: ' + source)
    current = json.loads((sweep / 'report.json').read_text())
    roots = dict(background=background, renderer=renderer, normal=normal, spans=spans)
    data = {k: verify_capture(p) for k, p in roots.items()}
    if not neutral(data['background'], data['normal']):
        raise ValueError('Background observer changed replay')
    baseline, timeline = data['normal']
    for name in ('renderer', 'spans'):
        receipt, rows = data[name]
        if (rows != timeline or receipt['rom_sha256'] != baseline['rom_sha256'] or
                receipt['audio_sha256'] != baseline['audio_sha256'] or
                receipt['scenario_sha256'] != baseline['scenario_sha256']):
            raise ValueError('Observer changed replay: ' + name)
    for name, root in (('snes', background), ('normal_snes', normal)):
        if current['sources'][name]['capture_sha256'] != sha(root / 'capture.json'):
            raise ValueError('Sweep does not bind current replay')
    if current['sources']['nes']['rom_sha256'] != old['captures']['nes']['rom_sha256']:
        raise ValueError('NES reference changed')
    selected = fixed_samples(old, current)
    trace = renderer.with_suffix('.csv')
    if data['renderer'][0].get('render_scroll_trace', {}).get('sha256') != sha(trace):
        raise ValueError('Renderer trace not bound by capture process')
    rendered = load_lines(trace, 'snes', [r['snes_frame'] for _, r in selected])
    span_trace = spans.with_name(spans.name + '-spans.csv')
    if data['spans'][0]['span_trace']['sha256'] != sha(span_trace):
        raise ValueError('CPU trace not bound')
    metadata = json.loads((spans / 'span-points.json').read_text())
    for source, digest in metadata['sources'].items():
        if sha(Path(source)) != digest:
            raise ValueError('CPU observation source changed')
    point, = [p for p in metadata['points'] if p['label'] == 'camera_exit']
    events = list(csv.reader(span_trace.open()))
    comparisons = []
    for before, now in selected:
        frame = now['snes_frame']
        raw = bytes.fromhex(timeline[frame-1]['game_ram_hex'])
        if (raw[0x42], int.from_bytes(raw[0xdc:0xde], 'little')) != (now['room'], now['camera']):
            raise ValueError('Sample state mismatch')
        event, = [r for r in events if int(r[0]) == point['index'] and int(r[1]) == frame]
        if int(event[5], 16) & 65535 != int(point['pc'], 16):
            raise ValueError('Wrong CPU hook')
        actual = bands(rendered[frame])
        comparisons.append(dict(**now, previous_rendered_bands=before['snes_rendered_bands'],
            nes_rendered_bands=before['nes_rendered_bands'], current_rendered_bands=actual,
            camera_hook=dict(line=int(event[2]), cycle=int(event[3]), clock=int(event[4])),
            sample_passed=actual == before['nes_rendered_bands'] and
                          now['background_playfield_differences'] == 0))
    result = dict(sample_passed=all(r['sample_passed'] for r in comparisons),
        full_sweep_passed=current['passed'], full_sweep_gates=current['gates'], comparisons=comparisons,
        observer_neutral=True, rom_sha256=baseline['rom_sha256'],
        sources={str(p): sha(p) for p in [Path(__file__), Path('tools/audit_render_scroll.py'),
            Path('tools/audit_background_sweep.py'), previous/'report.json', sweep/'report.json', trace,
            span_trace, spans/'span-points.json', *[r/'capture.json' for r in roots.values()]]},
        scope='Exact previous failed frames and game states, unchanged RGB555 image comparison and '
        'all actual renderer lines. Independent background/renderer/CPU timelines and PCM match normal. '
        'Targeted regression only; all full-sweep failures retained. Not speed or acoustic certification.')
    out.mkdir(parents=True)
    cards = []
    for row in comparisons:
        room, camera = row['room'], row['camera']
        cards.append('<h2>Room '+str(room)+', camera '+str(camera)+'</h2><pre>'+
                     html.escape(json.dumps(row, indent=2))+'</pre><section>')
        paths = [('NES reference', previous/f'nes-{room}-{camera}-background.png'),
                 ('Previous SNES', previous/f'snes-{room}-{camera}-background.png'),
                 ('Current SNES', background_path(background, data['background'][1][row['snes_frame']-1]))]
        for i, (label, path) in enumerate(paths):
            name = f'{room}-{camera}-{i}.png'
            shutil.copyfile(path, out/name)
            result['sources'][str(path)] = sha(path)
            cards.append(f'<figure><img src="{name}"><figcaption>{label}</figcaption></figure>')
        cards.append('</section>')
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Fixed-frame scrolling regression</title>'
        '<style>body{background:#101821;color:#eee;font:17px system-ui;margin:30px auto;max-width:1500px}'
        'a{color:#9df}section{display:flex}figure{margin:8px}img{width:448px;image-rendering:pixelated}</style>'
        '<h1>Fixed-frame renderer regression: '+('PASS' if result['sample_passed'] else 'FAIL')+'</h1><p>'+
        html.escape(result['scope'])+'</p><a href="report.json">Bound proof and retained full-sweep gates</a>'+''.join(cards))
    print(json.dumps(dict(sample_passed=result['sample_passed'], full_sweep_passed=result['full_sweep_passed'])))
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('previous', 'sweep', 'background', 'renderer', 'normal', 'spans', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    audit(**vars(p.parse_args()))
