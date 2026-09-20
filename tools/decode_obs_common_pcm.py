"""Decode complete observed PCM packets; never conceal lost packets with concatenation."""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha


def decode(text):
    records = [line.split(',') for line in text.splitlines() if line.strip()]
    if not records or records[0][0] != 'B' or records[-1][0] != 'Z':
        raise ValueError('Missing trace boundaries')
    begin, end = int(records[0][1]), int(records[-1][1])
    pairs, source, previous = {}, None, begin
    for row in records[1:-1]:
        kind = row[0]
        if kind not in ('I', 'M') or len(row) != 8:
            raise ValueError('Unknown, rejected or malformed PCM packet')
        clock, current, sequence, frames, stamp = map(int, row[1:6])
        if source is None:
            source = current
        if current != source or not begin <= previous <= clock <= end or not 0 < frames <= 1024:
            raise ValueError('Unexpected source, order or packet size')
        previous = clock
        pair = pairs.setdefault(sequence, {})
        if kind in pair:
            raise ValueError('Duplicate packet')
        if kind == 'I':
            fmt = int(row[6])
            if fmt not in (2, 3):
                raise ValueError('Unexpected interleaved input format')
            dtype = '<i2' if fmt == 2 else '<i4'
            payload = bytes.fromhex(row[7])
            if len(payload) != frames*2*np.dtype(dtype).itemsize:
                raise ValueError('Truncated interleaved PCM')
            pcm = np.frombuffer(payload, dtype=dtype).reshape(frames, 2)
        else:
            payloads = [bytes.fromhex(v) for v in row[6:8]]
            if any(len(v) != frames*4 for v in payloads):
                raise ValueError('Truncated planar PCM')
            pcm = np.column_stack([np.frombuffer(v, dtype='<f4') for v in payloads])
            if not np.isfinite(pcm).all():
                raise ValueError('Nonfinite PCM')
        pair[kind] = dict(clock=clock, timestamp=stamp, frames=frames, pcm=pcm)
    if not pairs or sorted(pairs) != list(range(1, len(pairs)+1)):
        raise ValueError('Missing packet sequence')
    if any(set(pair) != {'I', 'M'} for pair in pairs.values()):
        raise ValueError('Incomplete source/callback pair; do not conceal gap')
    kinds = {pair['I']['pcm'].dtype.str for pair in pairs.values()}
    if len(kinds) != 1:
        raise ValueError('Input format changed')
    inputs, common, index = [], [], []
    ia = ma = 0
    for sequence, pair in sorted(pairs.items()):
        i, m = pair['I'], pair['M']
        if i['clock'] > m['clock'] or i['timestamp'] != m['timestamp']:
            raise ValueError('Source/callback timestamp pairing changed')
        index.append(dict(sequence=sequence, input_first=ia, common_first=ma,
            input_frames=i['frames'], common_frames=m['frames'],
            input_clock=i['clock'], common_clock=m['clock'], timestamp=i['timestamp']))
        ia += i['frames']; ma += m['frames']
        inputs.append(i['pcm']); common.append(m['pcm'])
    return np.concatenate(inputs), np.concatenate(common), index


def run(capture, out):
    if out.exists():
        raise ValueError('Need fresh output')
    proof = bound_report(capture/'report.json')
    if proof['returncode'] or proof.get('deadline_failed') or not proof['same_obs_process'] or not proof['sources_unchanged']:
        raise ValueError('Unqualified observation')
    for name, digest in proof['artifacts'].items():
        if sha(capture/name) != digest:
            raise ValueError('Capture changed')
    if (capture/'stderr.txt').read_text().strip():
        raise ValueError('Warnings/errors: observation retained but not qualified')
    original, common, index = decode((capture/'pcm.csv').read_text())
    out.mkdir(parents=True, exist_ok=False)
    wavfile.write(out/'input.wav', 48000, original)
    wavfile.write(out/'common.wav', 48000, common)
    report = dict(packets=len(index), input_frames=len(original), common_frames=len(common),
        input_dtype=original.dtype.str, common_dtype=common.dtype.str, packet_index=index,
        changed_frame_packets=[r for r in index if r['input_frames'] != r['common_frames']],
        input_nonzero_samples=int(np.count_nonzero(original)),
        common_nonzero_samples=int(np.count_nonzero(common)),
        observer_neutral_verified=False, pop_free_verified=False,
        scope='Native packet payloads concatenated only after complete sequence/pair validation. '
              'Packet timestamps retained. No gap fill, gain normalization, retiming or resampling. '
              'OBS common float PCM is observed before monitor volume/resampling; input PCM is '
              'DeckLink interleaved PCM before OBS source processing. Both are upstream of the '
              'two previously compared branches, not an independent HDMI receiver.',
        sources={str(p): sha(p) for p in (Path(__file__), Path('tools/audit_main_display_latency.py'),
            Path('tools/benchmark_report.py'), capture/'report.json', capture/'pcm.csv', capture/'stderr.txt')},
        artifacts={p.name: sha(p) for p in out.iterdir()})
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('packet_index','sources','changed_frame_packets')}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    run(**vars(p.parse_args()))
