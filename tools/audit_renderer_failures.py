"""Retain missing-coverage failures while diagnosing other complete renderer frames.

This does not replace or relax the strict full-route release gates. A missing,
duplicate or unsupported line remains a failure, never an exclusion to earn PASS.
"""
import argparse
import csv
import html
import json
from pathlib import Path
import shutil

from tools.audit_camera_hold import held
from tools.audit_scroll_splits import eligible,neutral,scan
from tools.audit_scroll_publication import frame_path
from tools.benchmark_report import sha


def diagnose(rows,source):
    pairs=[(p,r) for p,r in zip(rows,rows[1:]) if eligible(p) and eligible(r)]
    grouped={r['frame']:[] for p,r in pairs}
    for raw in source:
        frame=int(raw['frame'])
        if frame in grouped:grouped[frame].append(raw)
    coverage=[];splits=[];stale=[];complete=0;held_count=0
    for previous,current in pairs:
        frame=current['frame'];raw=grouped[frame]
        try:rendered=scan(raw,[frame])
        except ValueError as error:
            observed=[int(r['line']) for r in raw]
            coverage.append(dict(frame=frame,error=str(error),observed_lines=observed,
                missing_lines=sorted(set(range(32,192))-set(observed))))
            continue
        complete+=1
        values=sorted(set(rendered[frame].values()))
        if len(values)>1:splits.append(dict(frame=frame,values=values))
        a,b=(bytes.fromhex(r['game_ram_hex']) for r in (previous,current))
        if len(a)!=2048 or len(b)!=2048:raise ValueError('Missing original RAM')
        if a[0x42]!=b[0x42] or (a[0xf6],a[0x3d]&1)!=(b[0xf6],b[0x3d]&1):continue
        result=held([previous,current],rendered)
        held_count+=result['checked_frames'];stale+=result['failures']
    if not pairs:raise ValueError('No eligible frames')
    return dict(passed=not (coverage or splits or stale),eligible_frames=len(pairs),
        complete_frames=complete,checked_held_frames=held_count,
        coverage_failures=coverage,splits=splits,stale_camera_failures=stale)


def audit(capture,normal,out):
    rows,trace=neutral(capture,normal)
    with trace.open() as stream:report=diagnose(rows,csv.DictReader(stream))
    out.mkdir(parents=True,exist_ok=False)
    cards=[]
    # Every distinct failed frame is retained; no favorable image selection.
    failed=sorted({r['frame'] for key in ('coverage_failures','splits','stale_camera_failures')
                   for r in report[key]})
    for frame in failed:
        src=frame_path(normal,rows[frame-1]);name=f'frame-{frame}.png'
        shutil.copyfile(src,out/name)
        cards.append(f'<figure><img src="{name}"><figcaption>Failed frame {frame}</figcaption></figure>')
    paths=[Path(__file__),Path('tools/audit_camera_hold.py'),Path('tools/audit_scroll_splits.py'),
        Path('tools/benchmark_report.py'),Path('tools/audit_scroll_publication.py'),
        capture/'capture.json',normal/'capture.json',trace]
    report.update(release_ready=False,sources={str(p):sha(p) for p in paths},
        images={str(p):sha(p) for p in out.glob('*.png')},
        scope='Full neutral renderer replay. Incomplete/unsupported/duplicate coverage remains FAIL; '
              'other complete frames are inspected for splits and extra-frame stale camera. '
              'Does not waive strict gates, certify tile content, acoustics or original-game speed.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    summary={k:v for k,v in report.items() if k not in ('sources','images')}
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Renderer failure evidence</title>'
        '<style>body{background:#101821;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}'
        'a{color:#9df}.grid{display:flex;flex-wrap:wrap}figure{margin:10px}img{width:384px;image-rendering:pixelated}'
        'pre{white-space:pre-wrap}</style><h1>Renderer failure evidence</h1><p><a href="report.json">Bound evidence</a></p>'
        '<pre>'+html.escape(json.dumps(summary,indent=2))+'</pre><div class="grid">'+''.join(cards)+'</div>')
    print(json.dumps({k:len(report[k]) for k in ('coverage_failures','splits','stale_camera_failures')}))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('capture','normal','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();audit(a.capture,a.normal,a.out)
