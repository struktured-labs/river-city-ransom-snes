"""Measure actual renderer camera holds, including stops, without speed claims."""
import argparse
from collections import Counter
import csv
import html
import json
from pathlib import Path

from tools.audit_render_scroll import nes_offset
from tools.benchmark_report import sha, verify_capture

PHASES = ('park_00_east_sweep', 'park_00_west_sweep')


def rendering_enabled(row,system):
    if system=='nes':
        return bool(row['nes_ppu']['mask'] & 8)
    return bool(row['native']['ppu_mask'] & 8) and row['native']['transition_state']==0


def cameras(records, system, frames):
    """Stream all pixel groups/lines, retaining split evidence and coverage."""
    wanted = set(frames)
    groups = 32 if system == 'nes' else 1
    observed = {}
    for raw in records:
        frame = int(raw['frame'])
        if frame not in wanted:
            continue
        r = {k:int(v) for k,v in raw.items()}
        line, group = r['line'], r['group'] if system == 'nes' else 0
        if not 32 <= line < 192 or not 0 <= group < groups:
            raise ValueError('Invalid renderer position')
        if system == 'snes' and (r['mode'] != 0 or not r['main_screen'] & 1 or r['forced_blank']):
            raise ValueError('Unsupported SNES renderer state')
        camera = nes_offset(r) if system == 'nes' else r['h_offset'] & 511
        sample = observed.setdefault(frame, dict(bits=0, values=set()))
        bit = 1 << ((line-32)*groups+group)
        if sample['bits'] & bit:
            raise ValueError('Duplicate renderer observation')
        sample['bits'] |= bit
        sample['values'].add(camera)
    complete = (1 << (160*groups))-1
    if set(observed) != wanted or any(s['bits'] != complete for s in observed.values()):
        raise ValueError('Incomplete renderer coverage')
    return {f:sorted(s['values']) for f,s in observed.items()}


def measure(series):
    if len(series) < 2:
        raise ValueError('Need consecutive rendered frames')
    changes = []
    for previous, current in zip(series, series[1:]):
        if current['frame'] != previous['frame']+1:
            raise ValueError('Nonconsecutive phase coverage')
        if not (0 <= previous['camera'] < 512 and 0 <= current['camera'] < 512):
            raise ValueError('Invalid camera')
        delta = ((current['camera']-previous['camera']+256)&511)-256
        if delta:
            changes.append(dict(frame=current['frame'],before=previous['camera'],
                                camera=current['camera'],delta=delta))
    intervals = [dict(start=a['frame'],end=b['frame'],frames=b['frame']-a['frame'],
                      camera=a['camera'],start_delta=a['delta'],end_delta=b['delta'])
                 for a,b in zip(changes,changes[1:])]
    # A regular two-pixel step repeated after 1 then 3 (or 3 then 1) frames is
    # a useful pacing diagnostic. Keep ALL other intervals; do not hide stops.
    paired = [dict(first=a,second=b) for a,b in zip(intervals,intervals[1:])
              if (a['frames'],b['frames']) in ((1,3),(3,1))
              and abs(a['start_delta']) == 2
              and a['start_delta'] == a['end_delta'] == b['end_delta']]
    return dict(frames=len(series),changes=changes,intervals=intervals,
        hold_histogram=dict(sorted(Counter(r['frames'] for r in intervals).items())),
        uniform_two_pixel_1_3_pairs=paired,
        leading_censored_hold=(changes[0]['frame']-series[0]['frame']) if changes else len(series),
        trailing_censored_hold=(series[-1]['frame']-changes[-1]['frame']+1) if changes else len(series),
        series=series)


def observe(capture, normal, system):
    receipt,rows=verify_capture(capture)
    baseline,reference=verify_capture(normal)
    if (receipt['system'] != system or baseline['system'] != system or rows != reference
        or not receipt['capture_complete'] or not baseline['capture_complete']
        or any(receipt[k] != baseline[k] for k in ('rom_sha256','scenario_sha256','audio_sha256','frames'))
        or any(r['fault'] or r['input_requested'] != r['input_delivered'] for r in rows)):
        raise ValueError('Need complete neutral fault-free replay')
    selected=[];excluded=[]
    for previous,row in zip(rows,rows[1:]):
        if row['phase'] not in PHASES:continue
        if rendering_enabled(previous,system) and rendering_enabled(row,system):
            selected.append(row)
        else:
            excluded.append(dict(frame=row['frame'],phase=row['phase'],
                reason='Rendering disabled/transition at current or previous boundary'))
    if {r['phase'] for r in selected} != set(PHASES):
        raise ValueError('Missing park phase')
    binding=receipt['render_scroll_trace'];trace=Path(binding['path'])
    if (sha(trace) != binding['sha256'] or binding['first'] > selected[0]['frame']
        or binding['last'] < selected[-1]['frame']):
        raise ValueError('Unbound or incomplete renderer trace')
    with trace.open() as source:
        rendered=cameras(csv.DictReader(source),system,[r['frame'] for r in selected])
    splits={f:v for f,v in rendered.items() if len(v)!=1}
    if splits:
        raise ValueError('Split camera; cannot treat it as a single displayed position: '+str(splits))
    results={p:measure([dict(frame=r['frame'],camera=rendered[r['frame']][0])
                        for r in selected if r['phase']==p]) for p in PHASES}
    return dict(rom_sha256=receipt['rom_sha256'],scenario_sha256=receipt['scenario_sha256'],
                phases=results,excluded_rendering_boundaries=excluded,observer_neutral=True,
                sources={str(p):sha(p) for p in (capture/'capture.json',normal/'capture.json',trace)})


def audit(manifest,out):
    config=json.loads(manifest.read_text())
    runs={name:observe(Path(r['capture']),Path(r['normal']),r['system']) for name,r in config.items()}
    if len({r['scenario_sha256'] for r in runs.values()}) != 1:
        raise ValueError('Different traversal policies')
    scope=('All actual background pixel groups/lines through rendering-enabled portions of both fixed park phases; '
           'blank/transition boundaries are individually retained as exclusions, and holes '
           'within the measured sequence fail rather than merging separated intervals. '
           'complete independent normal timelines and PCM must match. Histograms retain '
           'every complete camera hold, including long stops, with censored phase edges '
           'reported separately. Different encounters/input durations remain; this measures '
           'presentation cadence, not equal-work combat speed, intended player motion, '
           'input latency, audio quality or release readiness.')
    paths=[manifest,Path(__file__),Path('tools/audit_render_scroll.py'),Path('tools/benchmark_report.py'),
           Path('tools/fceumm_raster_scroll.inc'),Path('tools/snes9x_raster_scroll.inc')]
    report=dict(runs=runs,scope=scope,release_ready=False,sources={str(p):sha(p) for p in paths})
    out.mkdir(parents=True,exist_ok=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    cards=[]
    for name,run in runs.items():
        cards.append('<h2>'+html.escape(name)+'</h2><table><tr><th>Phase</th><th>Hold duration → count</th><th>Uniform 2px 1/3 pairs</th></tr>')
        for phase,result in run['phases'].items():
            cards.append('<tr><td>'+html.escape(phase)+'</td><td>'+html.escape(str(result['hold_histogram']))+
                         '</td><td>'+str(len(result['uniform_two_pixel_1_3_pairs']))+'</td></tr>')
        cards.append('</table>')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Displayed camera cadence</title>'
        '<style>body{background:#101821;color:#eef;font:17px system-ui;max-width:1250px;margin:30px auto}'
        'a{color:#9df}td,th{padding:9px;border:1px solid #567}table{border-collapse:collapse}</style>'
        '<h1>Actual displayed-camera holds</h1><p>'+html.escape(scope)+'</p>'
        '<p><a href="report.json">Every camera frame, interval and hash</a></p>'+''.join(cards))
    print(json.dumps({n:{p:dict(histogram=v['hold_histogram'],pairs=len(v['uniform_two_pixel_1_3_pairs']))
                        for p,v in r['phases'].items()} for n,r in runs.items()},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','out'):parser.add_argument('--'+name,type=Path,required=True)
    audit(**vars(parser.parse_args()))
