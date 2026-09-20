"""Expose isolated three-frame holds that a one/three-pair count can miss."""
import argparse
from collections import Counter
import html
import json
from pathlib import Path

from tools.audit_display_cadence import measure
from tools.benchmark_report import sha


def summarize(phase):
    # JSON serializes the histogram's integer keys as strings.
    if json.loads(json.dumps(measure(phase['series'])))!=json.loads(json.dumps(phase)):
        raise ValueError('Cadence series and derived intervals differ')
    uniform=[r for r in phase['intervals'] if abs(r['start_delta'])==2 and r['start_delta']==r['end_delta']]
    return dict(uniform_endpoint_holds=len(uniform),
        histogram=dict(sorted(Counter(r['frames'] for r in uniform).items())),
        short_irregular=[r for r in uniform if r['frames'] in (1,3,4)],
        long_holds=[r for r in uniform if r['frames']>4],
        pairs=len(phase['uniform_two_pixel_1_3_pairs']))


def audit(cadence,out):
    data=json.loads(cadence.read_text())
    for p,h in data['sources'].items():
        if sha(Path(p))!=h:raise ValueError('Changed cadence source')
    for run in data['runs'].values():
        for p,h in run['sources'].items():
            if sha(Path(p))!=h:raise ValueError('Changed cadence capture/renderer')
    runs={name:{phase:summarize(values) for phase,values in run['phases'].items()}
        for name,run in data['runs'].items()}
    report=dict(release_ready=False,runs=runs,sources={str(p):sha(p) for p in
        (Path(__file__),Path('tools/audit_display_cadence.py'),Path('tools/benchmark_report.py'),cadence)},
        scope='Recomputed bound cadence series; all holds with matching two-pixel endpoint steps, '
        'including isolated three-frame holds and long stops. A zero one/three-pair count is not a speed pass. '
        'Endpoint steps alone do not prove constant intended motion inside the interval or its CPU cause.')
    out.mkdir(parents=True,exist_ok=False);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    cards=[]
    for name,phases in runs.items():
        cards.append('<h2>'+html.escape(name)+'</h2><table><tr><th>Phase</th><th>All uniform-endpoint holds</th><th>1/3/4-frame holds</th><th>1/3 pairs</th></tr>')
        for phase,r in phases.items():
            cards.append(f'<tr><td>{html.escape(phase)}</td><td>{r["histogram"]}</td><td>{len(r["short_irregular"])}</td><td>{r["pairs"]}</td></tr>')
        cards.append('</table>')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Uniform-endpoint camera holds</title>'
        '<style>body{background:#101821;color:#eef;font:17px system-ui;max-width:1150px;margin:30px auto}a{color:#9df}'
        'td,th{padding:9px;border:1px solid #567}table{border-collapse:collapse}</style>'
        '<h1>Zero paired stutters is not a speed pass</h1><p>'+html.escape(report['scope'])+
        '</p><p><a href="report.json">Every irregular interval and retained long hold</a></p>'+''.join(cards))
    print(json.dumps({name:{p:dict(histogram=r['histogram'],short_irregular=len(r['short_irregular']),pairs=r['pairs'])
        for p,r in phases.items()} for name,phases in runs.items()},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('cadence','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
