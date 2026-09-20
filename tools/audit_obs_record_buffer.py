"""Account for observed recording-buffer mutations without claiming PCM fidelity."""
import argparse
from collections import Counter
import json
from pathlib import Path

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha


def analyze(text):
    widths = dict(B=2, Z=2, I=6, P=7, p=6, D=8, d=6)
    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        fields = line.split(',')
        if fields[0] not in widths or len(fields) != widths[fields[0]]:
            raise ValueError('Malformed trace')
        values = list(map(int, fields[1:]))
        if min(values) < 0:
            raise ValueError('Negative metadata')
        rows.append((fields[0], *values))
    counts = Counter(r[0] for r in rows)
    if counts['B'] != 1 or counts['Z'] != 1 or not counts['I']:
        raise ValueError('Missing boundaries/input')
    if rows[0][0] != 'B' or rows[-1][0] != 'Z':
        raise ValueError('Bad boundaries')
    # Perf delivery across CPUs need not be globally ordered. Sort by captured
    # monotonic event clock; source buffer transactions themselves hold a mutex.
    records = sorted(rows[1:-1], key=lambda r: r[1])
    sources = {r[3] for r in records if r[0] == 'I'}
    active, last, transactions, holes, initial_censored = {}, {}, [], [], []
    for r in records:
        kind, clock, tid, source = r[:4]
        if not rows[0][1] <= clock <= rows[-1][1] or source not in sources:
            raise ValueError('Clock/source outside observation')
        if kind == 'I':
            continue
        size, stamp = r[4:6]
        if size % 4:
            raise ValueError('Buffer is not float32-aligned')
        if kind in ('P', 'D'):
            if source in active:
                raise ValueError('Overlapping same-buffer transactions or lost end')
            if source in last and (size, stamp) != last[source][1:]:
                old_clock, old_size, old_stamp = last[source]
                holes.append(dict(source=source, previous_clock=old_clock, clock=clock,
                    byte_change=size-old_size, timestamp_change=stamp-old_stamp))
            row = dict(kind=kind, clock=clock, tid=tid, source=source,
                       before_bytes=size, before_timestamp=stamp)
            if kind == 'P':
                row['input_frames'] = r[6]
            else:
                row.update(mix_start=r[6], mix_end=r[7])
            active[source] = row
        else:
            if source not in active:
                if source in last:
                    raise ValueError('Orphan transaction end')
                initial_censored.append(dict(kind=kind, clock=clock, source=source))
                last[source] = (clock, size, stamp)
                continue
            row = active.pop(source)
            if row['kind'].lower() != kind or row['tid'] != tid:
                raise ValueError('Mismatched transaction end')
            row.update(end_clock=clock, after_bytes=size, after_timestamp=stamp,
                       delta_frames=(size-row['before_bytes'])//4)
            transactions.append(row)
            last[source] = (clock, size, stamp)
    producer = [r for r in transactions if r['kind'] == 'P']
    consumer = [r for r in transactions if r['kind'] == 'D']
    return dict(event_counts=dict(counts), transactions=transactions,
        producer_count=len(producer), consumer_count=len(consumer),
        producer_frame_delta_histogram=dict(Counter(r['delta_frames'] for r in producer)),
        consumer_frame_delta_histogram=dict(Counter(r['delta_frames'] for r in consumer)),
        non_append_producers=[r for r in producer if r['delta_frames'] != r['input_frames']],
        non_1024_consumers=[r for r in consumer if r['delta_frames'] != -1024],
        between_transaction_changes=holes, initial_censored=initial_censored,
        final_censored=list(active.values()),
        pcm_observed=False, observer_neutral_verified=False, capture_or_game_fixed=False)


def audit(capture, out):
    if out.exists():
        raise ValueError('Need fresh output')
    proof = bound_report(capture/'report.json')
    if proof['returncode'] or not proof['same_obs_process'] or not proof['sources_unchanged'] or proof.get('deadline_failed'):
        raise ValueError('Failed observation')
    for name, digest in proof['artifacts'].items():
        if sha(capture/name) != digest:
            raise ValueError('Artifact changed')
    stderr = (capture/'stderr.txt').read_text()
    if stderr.strip():
        raise ValueError('Observer warnings/errors retained; not qualified')
    result = analyze((capture/'packets.csv').read_text())
    result.update(scope=__doc__, capture=str(capture), sources={str(p): sha(p) for p in
        (Path(__file__), capture/'report.json', capture/'packets.csv', capture/'stderr.txt',
         Path('tools/audit_main_display_latency.py'), Path('tools/benchmark_report.py'))})
    out.mkdir(parents=True, exist_ok=False)
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('transactions', 'sources')}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    audit(**vars(p.parse_args()))
