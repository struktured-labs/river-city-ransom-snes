"""Audit metadata-only OBS monitor observations, not game audio fidelity.

Q observes successful resampling, before queue publication. Lock-busy exits
prove a skipped monitor callback in this instrumented run only. Uprobes may
alter timing; absence of lock contention does not exonerate earlier captures.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

from tools.benchmark_report import sha


WIDTHS = dict(B=2, Z=2, I=7, M=8, L=4, Q=4, E=3)


def analyze(text):
    records = []
    for line in text.splitlines():
        if not line.strip():
            continue
        fields = line.split(',')
        kind = fields[0]
        if kind not in WIDTHS or len(fields) != WIDTHS[kind]:
            raise ValueError('Unknown or malformed trace record')
        values = list(map(int, fields[1:]))
        if any(v < 0 for v in values):
            raise ValueError('Negative metadata')
        records.append((kind, *values))
    if not records or records[0][0] != 'B' or records[-1][0] != 'Z':
        raise ValueError('Missing trace boundary')
    counts = Counter(r[0] for r in records)
    if counts['B'] != 1 or counts['Z'] != 1 or not counts['I']:
        raise ValueError('Bad boundaries or no DeckLink observations')
    begin, end = records[0][1], records[-1][1]
    active, previous_clock, inputs, completed = {}, {}, [], []
    for r in records[1:-1]:
        kind, clock, tid = r[:3]
        if not begin <= clock <= end or clock < previous_clock.get(tid, begin):
            raise ValueError('Out-of-order event on one thread')
        previous_clock[tid] = clock
        if kind == 'I':
            _, _, _, source, frames, timestamp, rate = r
            if not frames or not rate:
                raise ValueError('Empty input packet or invalid rate')
            inputs.append(dict(clock=clock, tid=tid, source=source, frames=frames,
                               timestamp=timestamp, rate=rate))
        elif kind == 'M':
            if tid in active:
                raise ValueError('Nested callback or lost return')
            _, _, _, source, frames, timestamp, monitor, muted = r
            active[tid] = dict(clock=clock, tid=tid, source=source, frames=frames,
                               timestamp=timestamp, monitor=monitor, muted=muted,
                               lock=None, resampled_frames=None)
        else:
            if tid not in active:
                raise ValueError('Orphan monitor event')
            row = active[tid]
            if kind == 'L':
                if row['lock'] is not None:
                    raise ValueError('Duplicate lock observation')
                row['lock'] = r[3]
            elif kind == 'Q':
                if row['lock'] != 0 or row['resampled_frames'] is not None:
                    raise ValueError('Resample without successful lock or duplicate')
                row['resampled_frames'] = r[3]
            elif kind == 'E':
                if row['lock'] is None:
                    raise ValueError('Missing lock observation')
                row['duration_ns'] = clock-row['clock']
                completed.append(active.pop(tid))
    known = {r['source'] for r in inputs}
    if any(r['source'] not in known for r in completed + list(active.values())):
        raise ValueError('Monitor source not observed from DeckLink')
    input_keys = Counter((r['source'], r['timestamp'], r['frames']) for r in inputs)
    monitor_keys = Counter((r['source'], r['timestamp'], r['frames']) for r in completed)
    matched = sum((input_keys & monitor_keys).values())
    deltas, prior = [], {}
    for row in inputs:
        old = prior.get(row['source'])
        if old:
            deltas.append(dict(source=row['source'], timestamp=row['timestamp'],
                arrival_delta_ns=row['clock']-old['clock'],
                timestamp_delta_ns=row['timestamp']-old['timestamp'],
                expected_delta_ns=old['frames']*1_000_000_000/old['rate'],
                timestamp_residual_ns=row['timestamp']-old['timestamp']-
                    old['frames']*1_000_000_000/old['rate']))
        prior[row['source']] = row
    busy = [r for r in completed if r['lock'] != 0]
    no_resample = [r for r in completed if r['lock'] == 0 and r['resampled_frames'] is None]
    resized = [r for r in completed if r['resampled_frames'] is not None and
               r['frames'] != r['resampled_frames']]
    return dict(event_counts=dict(counts), duration_ns=end-begin,
        input_packets=len(inputs), completed_callbacks=len(completed),
        exact_input_monitor_matches=matched,
        unmatched_input_keys=[list(k)+[v] for k, v in (input_keys-monitor_keys).items()],
        unmatched_monitor_keys=[list(k)+[v] for k, v in (monitor_keys-input_keys).items()],
        censored_callbacks=list(active.values()), lock_busy_callbacks=busy,
        locked_without_successful_resample=no_resample, resized_callbacks=resized,
        input_frames=sum(r['frames'] for r in inputs),
        monitor_input_frames=sum(r['frames'] for r in completed),
        resampled_frames=sum(r['resampled_frames'] or 0 for r in completed),
        lock_busy_skipped_frames=sum(r['frames'] for r in busy),
        input_timing=deltas, callbacks=completed,
        successful_queue_publication_observed=False,
        observer_neutral_verified=False, physical_audio_fixed=False)


def audit(capture, out):
    if out.exists():
        raise ValueError('Need fresh report path')
    proof_path = capture/'report.json'
    proof = json.loads(proof_path.read_text())
    if proof['returncode'] or not proof['same_obs_process'] or not proof['sources_unchanged']:
        raise ValueError('Unqualified capture process')
    for name, digest in proof['sources'].items():
        if sha(Path(name)) != digest:
            raise ValueError('Capture source changed: '+name)
    for name, digest in proof['artifacts'].items():
        if sha(capture/name) != digest:
            raise ValueError('Capture artifact changed: '+name)
    errors = (capture/'stderr.txt').read_text()
    if any(s in errors.lower() for s in ('lost', 'error', 'failed')):
        raise ValueError('Observer errors or lost events; retained capture is not complete')
    result = analyze((capture/'packets.csv').read_text())
    result.update(scope=__doc__, capture=str(capture),
        sources={str(p): sha(p) for p in (Path(__file__), proof_path,
                 capture/'packets.csv', capture/'stderr.txt', Path('tools/benchmark_report.py'))})
    out.mkdir(parents=True, exist_ok=False)
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k not in
                     ('input_timing', 'callbacks', 'sources')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    audit(**vars(parser.parse_args()))
