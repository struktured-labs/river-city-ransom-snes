"""Require every byte of every bounded callback; no partial-packet recovery."""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha


def decode(text):
    rows = [r.split(',') for r in text.splitlines() if r.strip()]
    if (not rows or len(rows[0]) != 2 or len(rows[-1]) != 2 or
            rows[0][0] != 'B' or rows[-1][0] != 'Z'):
        raise ValueError('Missing capture boundaries')
    begin, end = int(rows[0][1]), int(rows[-1][1])
    if end <= begin:
        raise ValueError('Invalid capture clocks')
    previous, source, pending = begin, None, None
    pairs, sequence = [], 0
    for row in rows[1:-1]:
        kind = row[0]
        if kind in ('I', 'M'):
            if pending is not None or len(row) != (7 if kind == 'I' else 6):
                raise ValueError('Truncated/overlapping callback')
            clock, current, seq, frames, stamp = map(int, row[1:6])
            if source is None:
                source = current
            if current != source or not previous <= clock <= end or not 0 < frames <= 8192:
                raise ValueError('Changed source, clock order or packet bound')
            previous = clock
            if kind == 'I':
                if seq != sequence+1 or (pairs and 'M' not in pairs[-1]):
                    raise ValueError('Missing, duplicate or unpaired input sequence')
                sequence = seq
                fmt = int(row[6])
                if fmt not in (2, 3):
                    raise ValueError('Unsupported input format')
                pairs.append({})
            else:
                if not pairs or seq != sequence or 'M' in pairs[-1] or 'I' not in pairs[-1]:
                    raise ValueError('Unpaired or duplicate common header')
                fmt = 4
            pending = dict(kind=kind, frames=frames, timestamp=stamp, clock=clock,
                           source=current, seq=seq, format=fmt, offset=0, payloads=[])
        elif kind == 'D':
            if pending is None or len(row) != (7 if pending['kind'] == 'I' else 8):
                raise ValueError('Payload without matching header')
            current, seq, offset, count = map(int, row[2:6])
            if (row[1] != pending['kind'] or current != source or seq != pending['seq'] or
                    offset != pending['offset'] or count != min(1024, pending['frames']-offset)):
                raise ValueError('Skipped/overlapping/changed chunk')
            payloads = [bytes.fromhex(v) for v in row[6:]]
            width = (4 if pending['format'] == 2 else 8) if pending['kind'] == 'I' else 4
            if any(len(p) != count*width for p in payloads):
                raise ValueError('Truncated chunk payload')
            pending['payloads'].append(payloads)
            pending['offset'] += count
            if pending['offset'] == pending['frames']:
                blocks = [b''.join(c[channel] for c in pending['payloads']) for channel in range(len(payloads))]
                if pending['kind'] == 'I':
                    dtype = '<i2' if pending['format'] == 2 else '<i4'
                    pcm = np.frombuffer(blocks[0], dtype=dtype).reshape(-1, 2)
                else:
                    pcm = np.column_stack([np.frombuffer(p, dtype='<f4') for p in blocks])
                    if not np.isfinite(pcm).all():
                        raise ValueError('Nonfinite common samples')
                pending['pcm'] = pcm
                del pending['payloads']
                pairs[-1][pending['kind']] = pending
                pending = None
        else:
            raise ValueError('Rejected or unknown record; full observation unqualified')
    if pending is not None or not pairs or any(set(p) != {'I', 'M'} for p in pairs):
        raise ValueError('Incomplete capture pairs')
    if len({p['I']['pcm'].dtype.str for p in pairs}) != 1:
        raise ValueError('Input format changed')
    index, inputs, common = [], [], []
    ia = ma = 0
    for seq, pair in enumerate(pairs, 1):
        i, m = pair['I'], pair['M']
        if i['timestamp'] != m['timestamp'] or i['clock'] > m['clock']:
            raise ValueError('Source/common timestamp mismatch')
        index.append(dict(sequence=seq, input_first=ia, common_first=ma,
                          input_frames=i['frames'], common_frames=m['frames'],
                          input_clock=i['clock'], common_clock=m['clock'], timestamp=i['timestamp']))
        ia += i['frames']; ma += m['frames']
        inputs.append(i['pcm']); common.append(m['pcm'])
    return np.concatenate(inputs), np.concatenate(common), index


def run(capture, out):
    if out.exists():
        raise ValueError('Fresh output required')
    proof = bound_report(capture/'report.json')
    if (proof['returncode'] or proof.get('deadline_failed') or not proof['same_obs_process'] or
            not proof['sources_unchanged'] or (capture/'stderr.txt').read_text().strip()):
        raise ValueError('Unqualified observation')
    for p, digest in proof['artifacts'].items():
        if sha(capture/p) != digest:
            raise ValueError('Changed capture')
    original, common, index = decode((capture/'pcm.csv').read_text())
    scale = 32768 if original.dtype.itemsize == 2 else 2147483648
    exact = original.shape == common.shape and np.array_equal(original.astype(np.float32)/scale, common)
    # Host timestamps can jitter. Retain all residuals rather than pretending
    # sequence completeness proves contiguous device sampling across a reset.
    timing = [dict(sequence=b['sequence'],
                   timestamp_delta_ns=b['timestamp']-a['timestamp'],
                   sample_duration_ns=a['input_frames']*1e9/48000,
                   residual_ns=b['timestamp']-a['timestamp']-a['input_frames']*1e9/48000)
              for a, b in zip(index, index[1:])]
    out.mkdir(parents=True)
    wavfile.write(out/'input.wav', 48000, original)
    wavfile.write(out/'common.wav', 48000, common)
    report = dict(packets=len(index), input_frames=len(original), common_frames=len(common),
                  packet_index=index, timestamp_intervals=timing,
                  input_dtype=original.dtype.str, input_common_exact_conversion=exact,
                  large_packets=[r for r in index if max(r['input_frames'], r['common_frames']) > 1024],
                  observer_neutral_verified=False, pop_free_verified=False,
                  sources={str(p): sha(p) for p in (Path(__file__), Path('tools/benchmark_report.py'),
                      Path('tools/audit_main_display_latency.py'), capture/'report.json', capture/'pcm.csv', capture/'stderr.txt')},
                  artifacts={p.name: sha(p) for p in out.iterdir()},
                  scope='Every bounded callback reconstructed from contiguous exact-size chunks. '
                  'No dropped/repaired packets, normalization or resampling. Device continuity '
                  'is NOT inferred from callback completeness: all host timestamp residuals '
                  'retained, including HDMI reacquisition. Probe overhead remains unqualified.')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ('packets', 'input_frames', 'common_frames',
                                           'input_common_exact_conversion', 'large_packets')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('capture', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    run(**vars(parser.parse_args()))
