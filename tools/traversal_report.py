"""Build a verified, phase-aligned walking contact sheet; no release verdict."""
import argparse
import json
import shutil
from pathlib import Path

try:
    from .benchmark_report import verify_capture, phase_metrics, sha
except ImportError:
    from benchmark_report import verify_capture, phase_metrics, sha


def build(reference, candidate, out):
    evidence = [verify_capture(p) for p in (reference, candidate)]
    if any(r['scenario_name'] not in ('traversal', 'traversal-recovery') or not r['capture_complete'] for r, _ in evidence):
        raise ValueError('Need two completed traversal captures')
    if evidence[0][0]['scenario_name'] != evidence[1][0]['scenario_name']:
        raise ValueError('Traversal schedules differ')
    if [r['system'] for r, _ in evidence] != ['nes', 'snes']:
        raise ValueError('Expected original NES followed by candidate SNES')
    out.mkdir(parents=True, exist_ok=False)
    report = dict(schema='rcr-traversal-audit-v1', release_ready=False,
                  scope='Street-start aligned inputs; not position-matched gameplay or a scene-exit oracle',
                  captures={}, phases=[])
    html = ['<!doctype html><meta charset="utf-8"><title>RCR traversal audit</title>',
            '<style>body{background:#161820;color:#eee;font:16px sans-serif;max-width:1100px;margin:auto}'
            'section{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:30px 0}'
            'img{width:100%;image-rendering:pixelated}pre{white-space:pre-wrap}h2{grid-column:1/-1}</style>',
            '<h1>NES / SNES walking audit</h1><p>Same input duration after recognized street entry. '
            'Gameplay positions diverge. This is diagnostic evidence, not a scrolling, speed, or audio pass.</p>']
    for system, directory, (receipt, rows) in zip(('nes', 'snes'), (reference, candidate), evidence):
        report['captures'][system] = dict(capture_sha256=sha(directory/'capture.json'),
                                          rom_sha256=receipt['rom_sha256'])
        shutil.copyfile(directory/'audio.wav', out/f'{system}.wav')
        shutil.copyfile(directory/'capture.json', out/f'{system}-capture.json')
        html.append(f'<p>{system.upper()} full capture audio <audio controls src="{system}.wav"></audio></p>')
    phases = [p for p in evidence[0][0]['scenario'] if p['name'].startswith(('right_', 'left_'))]
    for phase in phases:
        name = phase['name']
        direction, index = name.split('_')
        duration = (int(index)+1)*120
        pair = dict(phase=name, direction=direction, held_direction_frames=duration)
        html.append(f'<section><h2>{direction.title()} held for {duration} display frames</h2>')
        for system, directory, (receipt, rows) in zip(('nes', 'snes'), (reference, candidate), evidence):
            group = [r for r in rows if r['phase'] == name]
            raw = bytes.fromhex(group[-1]['game_ram_hex'])
            metrics = phase_metrics(group)
            metrics['raw_dc_dd'] = raw[0xdc:0xde].hex()
            metrics['fault_frames'] = sum(bool(r['fault']) for r in group)
            pair[system] = metrics
            filename = f'{system}-{name}.png'
            shutil.copyfile(directory/f'{name}.png', out/filename)
            html.append(f'<div><h3>{system.upper()}</h3><img src="{filename}" alt="{system} {name}">'
                        f'<pre>{json.dumps(metrics, indent=2)}</pre></div>')
        report['phases'].append(pair)
        html.append('</section>')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    (out/'index.html').write_text('\n'.join(html))
    (out/'bundle.json').write_text(json.dumps(dict(schema='rcr-traversal-bundle-v1',
        files={p.name:sha(p) for p in sorted(out.iterdir())}), indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('reference', 'candidate', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    build(args.reference, args.candidate, args.out)
    print(args.out/'index.html')
