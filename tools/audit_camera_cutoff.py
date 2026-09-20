"""Classify every end-of-frame camera warning using neutral CPU entry timing.

Camera-tail entry is not the beam latch or completed camera store. Counts here
are diagnostic observations, not a relaxed replacement for deadline gates.
"""
import argparse
from collections import Counter, defaultdict
import csv
import html
import json
from pathlib import Path
import shutil

from tools.audit_camera_cadence import load
from tools.audit_scroll_splits import eligible, neutral, scan
from tools.audit_scroll_publication import frame_path
from tools.benchmark_report import sha


def classify(rows, events, rendered):
    by_frame = defaultdict(list)
    for event in events:
        by_frame[event['frame']].append(event)
    warnings = []
    checked = 0
    for previous, row in zip(rows, rows[1:]):
        if not eligible(previous) or not eligible(row):
            continue
        frame = row['frame']
        if frame != previous['frame'] + 1:
            raise ValueError('Nonconsecutive timeline')
        lines = rendered.get(frame, {})
        if set(lines) != set(range(32, 192)):
            raise ValueError('Incomplete street renderer')
        raw = bytes.fromhex(row['game_ram_hex'])
        if len(raw) != 2048:
            raise ValueError('Incomplete original RAM')
        expected = raw[0xf6] | ((raw[0x3d] & 1) << 8)
        actual = sorted(set(lines.values()))
        checked += 1
        if actual == [expected]:
            continue
        entries = by_frame[frame]
        category = ('no_entry' if not entries else 'multiple_entries' if len(entries) > 1
                    else 'entry_before_line31' if entries[0]['line'] < 31 else 'entry_at_or_after_line31')
        warnings.append(dict(frame=frame, committed_at_frame_end=expected,
                             rendered=actual, category=category, entries=entries))
    if not checked:
        raise ValueError('No eligible frames')
    return dict(checked_frames=checked, warning_count=len(warnings),
                counts=dict(Counter(r['category'] for r in warnings)), warnings=warnings)


def observe(cpu, raster, normal):
    receipt, rows, events, trace = load(cpu, normal, 'snes')
    render_rows, render_trace = neutral(raster, normal)
    if rows != render_rows:
        raise ValueError('Different CPU and renderer execution')
    frames = [r['frame'] for p, r in zip(rows, rows[1:]) if eligible(p) and eligible(r)]
    with render_trace.open() as stream:
        rendered = scan(csv.DictReader(stream), frames)
    report = classify(rows, events, rendered)
    report.update(rom_sha256=receipt['rom_sha256'], scenario_sha256=receipt['scenario_sha256'],
                  sources={str(p): sha(p) for p in (cpu/'capture.json', cpu/'span-points.json',
                      raster/'capture.json', normal/'capture.json', trace, render_trace)})
    return report, rows


def audit(before_cpu, before_raster, before_normal, after_cpu, after_raster, after_normal, out):
    before, old = observe(before_cpu, before_raster, before_normal)
    after, new = observe(after_cpu, after_raster, after_normal)
    if before['scenario_sha256'] != after['scenario_sha256']:
        raise ValueError('Different traversal policies')
    scope = ('All eligible end-of-frame camera warnings retained, classified by the actual '
             'camera-tail entry beam. Entry precedes the guard latch/stores; a late-line30 entry '
             'can latch line31. These counts do not certify missed deadlines, overall latency, '
             'combat-speed parity or acoustic quality. Each CPU/renderer replay must separately '
             'match its complete normal-core timeline and PCM. The candidate may change execution '
             'timing and PCM relative to the parent. Original sweep gates are unchanged.')
    out.mkdir(parents=True, exist_ok=False)
    cards = []
    samples = []
    # Retain both the discovered improvement and the countervailing change.
    for frame in (2531, 1440):
        sample = dict(frame=frame, sides={})
        cards.append(f'<h2>Frame {frame}</h2><div class="grid">')
        for label, rows, normal, result in (('before',old,before_normal,before), ('after',new,after_normal,after)):
            row = rows[frame-1]
            raw = bytes.fromhex(row['game_ram_hex'])
            sample['sides'][label] = dict(committed=raw[0xf6] | ((raw[0x3d]&1)<<8),
                warnings=[r for r in result['warnings'] if r['frame']==frame])
            name = f'{label}-{frame}.png'
            shutil.copyfile(frame_path(normal,row),out/name)
            cards.append(f'<figure><img src="{name}"><figcaption>{label}: original complete frame, '
                         f'committed camera {sample["sides"][label]["committed"]}</figcaption></figure>')
        cards.append('</div>')
        samples.append(sample)
    report = dict(before=before,after=after,samples=samples,scope=scope,release_ready=False,
                  sources={str(p):sha(p) for p in (Path(__file__),Path('tools/audit_camera_cadence.py'),
                      Path('tools/audit_scroll_splits.py'),Path('tools/audit_park_spans.py'))},
                  images={p.name:sha(p) for p in out.glob('*.png')})
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    summary={s:{k:r[k] for k in ('checked_frames','warning_count','counts')} for s,r in (('before',before),('after',after))}
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Camera cutoff experiment</title>'
        '<style>body{background:#101821;color:#eef;font:17px system-ui;max-width:1150px;margin:30px auto}'
        'a{color:#9df}.grid{display:grid;grid-template-columns:1fr 1fr}img{width:100%;image-rendering:pixelated}'
        'figure{margin:10px}pre{white-space:pre-wrap}</style><h1>One more safe camera-publication scanline</h1>'
        '<p>Experimental, not deployed. Includes both an earlier camera and a later camera counterexample.</p>'
        '<p>'+html.escape(scope)+'</p><pre>'+html.escape(json.dumps(summary,indent=2))+'</pre>'
        '<p><a href="report.json">Every warning and bound source</a> · '
        '<a href="../camera-line30-oracle-645/report.json">123 executed beam cases, six mutants</a> · '
        '<a href="../camera-line30-splits-640/">Full-route split audit</a></p>'+''.join(cards))
    print(json.dumps(summary,indent=2))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('before-cpu','before-raster','before-normal','after-cpu','after-raster','after-normal','out'):
        parser.add_argument('--'+name,type=Path,required=True)
    audit(**vars(parser.parse_args()))
