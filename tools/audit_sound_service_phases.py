"""Decompose sound-driver return spacing into entry spacing and execution change."""
import argparse
import csv
import json
from pathlib import Path
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha

MS_PER_CLOCK = 11000 / 236250000


def pair(events):
    calls = []
    active = None
    previous_clock = -1
    for row in events:
        kind, frame, line, cycle, clock = map(int, row[:5])
        if clock < previous_clock:
            raise ValueError('Nonmonotonic clock')
        previous_clock = clock
        if kind not in (0, 1):
            continue
        event = dict(frame=frame, line=line, cycle=cycle, clock=clock,
                     pc=row[5], stack=int(row[10]), native_id=int(row[13]))
        if kind == 0:
            if active is not None:
                raise ValueError('Nested or missing driver return')
            active = event
        else:
            if active is None or active['stack'] != event['stack']:
                raise ValueError('Unmatched driver return')
            duration = clock - active['clock']
            if duration <= 0:
                raise ValueError('Nonpositive driver duration')
            calls.append(dict(entry=active, returned=event, duration_clocks=duration,
                              duration_ms=duration * MS_PER_CLOCK))
            active = None
    if active is not None:
        raise ValueError('Terminal censored driver call')
    if len(calls) < 2:
        raise ValueError('Insufficient calls')
    intervals = []
    for a, b in zip(calls, calls[1:]):
        entry = b['entry']['clock'] - a['entry']['clock']
        delta = b['duration_clocks'] - a['duration_clocks']
        returned = b['returned']['clock'] - a['returned']['clock']
        if entry + delta != returned:
            raise ValueError('Invalid decomposition')
        intervals.append(dict(previous=a, current=b, entry_gap_ms=entry * MS_PER_CLOCK,
                              duration_change_ms=delta * MS_PER_CLOCK,
                              return_gap_ms=returned * MS_PER_CLOCK))
    return calls, intervals


def audit(capture, out):
    if out.exists():
        raise ValueError('Fresh report required')
    proof = bound_report(capture / 'sound-service.json')
    if not proof['observer_neutral']:
        raise ValueError('Non-neutral observation')
    with Path(proof['trace']).open() as stream:
        calls, intervals = pair(csv.reader(stream))
    focus = [r for r in intervals if 2118 <= r['current']['entry']['frame'] <= 2122]
    sources = dict(proof['sources'])
    for path in (Path(__file__), capture / 'sound-service.json'):
        sources[str(path)] = sha(path)
    report = dict(sources=sources, calls=calls, intervals=intervals, focus=focus,
                  call_count=len(calls), complete_pairs=True, release_ready=False,
                  scope=__doc__ + ' All calls retained, including transitions. Focus frame numbers '
                  'are CPU observer frames, not native PCM callback frames. This does not directly '
                  'join SPC packet IDs, exclude SPC delay, or certify acoustic correctness.')
    out.mkdir(parents=True)
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(calls=len(calls), focus=[dict(frame=r['current']['entry']['frame'],
        entry_gap_ms=r['entry_gap_ms'], duration_change_ms=r['duration_change_ms'],
        return_gap_ms=r['return_gap_ms']) for r in focus])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('capture', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    audit(**vars(parser.parse_args()))
