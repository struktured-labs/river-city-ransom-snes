"""Measure actual NMI spacing independently of producer call ordering."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path

from tools.audit_park_spans import parse, stable, FRAME_CLOCKS
from tools.benchmark_report import sha, verify_capture


def intervals(rows):
    entries = [i for i,r in enumerate(rows) if r['event'] == 0]
    measured, excluded = [], []
    for a,b in zip(entries,entries[1:]):
        first,last=rows[a],rows[b]
        gap=dict(first_frame=first['frame'],last_frame=last['frame'],
                 clocks=last['clock']-first['clock'],
                 nominal_frames=(last['clock']-first['clock'])/FRAME_CLOCKS,
                 first_line=first['line'],last_line=last['line'])
        if all(stable(r) for r in rows[a:b+1]):
            measured.append(gap)
        else:
            excluded.append(gap)
    if not measured:
        raise ValueError('No stable park NMI intervals')
    return dict(intervals=len(measured),
        frame_spans=dict(Counter(g['last_frame']-g['first_frame'] for g in measured)),
        clock_range=[min(g['clocks'] for g in measured),max(g['clocks'] for g in measured)],
        late=[g for g in measured if g['clocks']>1.5*FRAME_CLOCKS],
        excluded_intervals=excluded,
        scope='All consecutive actual NMI-entry pairs; stable park required throughout each interval. '
              'Excluded transitions/menus retained. Independent of graphics stage adjacency.')


def observe(capture,normal):
    receipt,rows=verify_capture(capture);control,baseline=verify_capture(normal)
    if (not receipt['capture_complete'] or receipt['system']!='snes' or rows!=baseline or
        any(receipt[k]!=control[k] for k in ('rom_sha256','audio_sha256','scenario_sha256','frames'))):
        raise ValueError('Incomplete or non-neutral observer')
    binding=receipt['span_trace'];trace=Path(binding['path'])
    if sha(trace)!=binding['sha256']:
        raise ValueError('Changed NMI span trace')
    with trace.open() as stream:
        events=parse(csv.reader(stream),binding)
    return dict(**intervals(events),trace_first=binding['first'],trace_last=binding['last'],
        rom_sha256=receipt['rom_sha256'],observer_neutral=True,
        sources={str(p):sha(p) for p in (capture/'capture.json',normal/'capture.json',trace)})


def audit(capture,normal,negative,negative_normal,out):
    candidate=observe(capture,normal);control=observe(negative,negative_normal)
    result=dict(passed=not candidate['late'] and bool(control['late']),release_ready=False,
        candidate=candidate,negative=control,
        sources={str(p):sha(p) for p in (Path(__file__),Path('tools/audit_park_spans.py'),
            Path('tools/benchmark_report.py'))},
        scope='Actual NMI cadence and known missed-VBlank negative control; no matched-combat, '
              'input-latency, renderer-content or perceptual audio verdict.')
    out.mkdir(parents=True,exist_ok=False)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=result['passed'],stable_intervals=candidate['intervals'],
        clock_range=candidate['clock_range'],late=len(candidate['late']),negative_late=len(control['late']))))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('capture','normal','negative','negative-normal','out'):
        parser.add_argument('--'+name,required=True,type=Path)
    audit(**vars(parser.parse_args()))
