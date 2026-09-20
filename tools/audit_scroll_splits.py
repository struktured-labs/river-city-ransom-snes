"""Detect actual within-street camera splits over a complete neutral replay."""
import argparse
import csv
import html
import json
from pathlib import Path

from tools.audit_render_scroll import bands, load_lines
from tools.benchmark_report import sha, verify_capture


def eligible(row):
    n = row['native']
    return n['task'] & 192 == 192 and n['transition_state'] == 0 and bool(n['ppu_mask'] & 8)


def scan(source, frames):
    selected = {f:{} for f in frames}
    for r in source:
        f, line = int(r['frame']), int(r['line'])
        if f not in selected:
            continue
        if (not 32 <= line < 192 or int(r['mode']) != 0 or
                not int(r['main_screen']) & 1 or int(r['forced_blank'])):
            raise ValueError('Unsupported selected renderer state')
        if line in selected[f]:
            raise ValueError('Duplicate selected renderer line')
        selected[f][line] = int(r['h_offset']) & 511
    if not selected or any(set(lines) != set(range(32,192)) for lines in selected.values()):
        raise ValueError('Missing eligible renderer coverage')
    return selected


def neutral(capture, normal):
    observed, rows = verify_capture(capture)
    control, timeline = verify_capture(normal)
    if (rows != timeline or not observed['capture_complete'] or
            any(observed[k] != control[k] for k in ('rom_sha256','scenario_sha256','audio_sha256','frames'))):
        raise ValueError('Renderer changed complete execution')
    trace = capture.with_suffix('.csv')
    if observed['render_scroll_trace']['sha256'] != sha(trace):
        raise ValueError('Unbound renderer trace')
    return rows, trace


def audit(capture, normal, negative, negative_normal, negative_frames, out):
    rows, trace = neutral(capture, normal)
    frames = [r['frame'] for p,r in zip(rows,rows[1:]) if eligible(p) and eligible(r)]
    with trace.open() as source:
        rendered = scan(csv.DictReader(source), frames)
    splits = [dict(frame=f,bands=bands(lines)) for f,lines in rendered.items() if len(set(lines.values()))>1]
    _, bad_trace = neutral(negative,negative_normal)
    bad = load_lines(bad_trace,'snes',negative_frames)
    bad_splits = [dict(frame=f,bands=bands(lines)) for f,lines in bad.items() if len(set(lines.values()))>1]
    if not bad_splits:
        raise ValueError('Known broken renderer control not detected')
    by_frame = {r['frame']:r for r in rows}
    lag=[]
    for f,lines in rendered.items():
        ram=bytes.fromhex(by_frame[f]['game_ram_hex'])
        committed=ram[0xf6] | ((ram[0x3d]&1)<<8)
        if set(lines.values()) != {committed}:
            lag.append(dict(frame=f,committed_at_frame_end=committed,bands=bands(lines)))
    out.mkdir(parents=True,exist_ok=False)
    paths=[Path(__file__),Path('tools/audit_render_scroll.py'),trace,bad_trace,
           *[r/'capture.json' for r in (capture,normal,negative,negative_normal)]]
    report=dict(split_free=not splits,release_ready=False,eligible_frames=len(frames),
        renderer_lines=len(frames)*160,splits=splits,negative_splits=bad_splits,
        frame_end_camera_differences=lag,sources={str(p):sha(p) for p in paths},
        scope='Complete neutral replay; consecutive frame boundaries require active game task, '
              'visible BG and no transition. All160 actual renderer lines required in every '
              'eligible frame, without alignment or selected stable positions. Split freedom '
              'is not camera-latency, original-speed, sprite or acoustic certification. '
              'End-of-frame committed camera may have changed after rendering; differences '
              'remain explicit and do not alone prove a missed deadline.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Full-route scroll split audit</title>'
        '<style>body{background:#101821;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}'
        'a{color:#9df}pre{white-space:pre-wrap}</style><h1>Actual renderer: full-route split audit</h1><p>'+
        html.escape(report['scope'])+'</p><p><a href="report.json">All measured frames and bound sources</a></p>'+
        f'<p>{len(frames)} eligible frames, {len(frames)*160} lines; {len(splits)} split frames. '
        f'{len(lag)} frame-end committed-camera differences remain recorded.</p><h2>Known broken control</h2><pre>'+
        html.escape(json.dumps(bad_splits,indent=2))+'</pre>')
    print(json.dumps(dict(split_free=not splits,frames=len(frames),splits=len(splits),
                         frame_end_camera_differences=len(lag),negative_splits=len(bad_splits))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('capture','normal','negative','negative-normal','out'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--negative-frames',type=int,nargs='+',required=True)
    audit(**vars(p.parse_args()))
