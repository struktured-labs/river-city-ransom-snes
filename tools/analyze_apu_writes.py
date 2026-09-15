"""Analyze raw adapter APU writes; repeated writes are not deduplicated."""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path


def analyze(rows):
    groups = collections.defaultdict(list)
    counts = collections.Counter()
    frames = collections.Counter()
    previous = -1
    total = 0
    for row in rows:
        if len(row) != 7:
            raise ValueError('Expected frame,line,cycle,NMI,address,value,PC')
        frame, line, cycle, nmi, address, value = map(int, row[:6])
        pc = int(row[6], 16)
        if (frame < previous or not 0 <= line < 262 or cycle < 0
                or not 0 <= nmi <= 65535 or not 0x4000 <= address <= 0x4017
                or not 0 <= value <= 255 or not 0xC1 <= pc >> 16 <= 0xC8):
            raise ValueError('Invalid or unordered APU write trace')
        previous = frame
        groups[frame, address].append(value)
        counts[f'{address:04x}'] += 1
        frames[frame] += 1
        total += 1
    if not total:
        raise ValueError('Empty APU trace is not evidence')
    repeated = [dict(frame=frame, register=f'{address:04x}', values=values)
                for (frame, address), values in groups.items() if len(values) > 1]
    return dict(schema='rcr-apu-write-analysis-v1', writes=total,
                writes_by_register=dict(sorted(counts.items())),
                raw_core_frame_range=[min(frames), max(frames)],
                max_writes_per_core_frame=max(frames.values()),
                repeated_register_frame_groups=len(repeated),
                changing_register_frame_groups=sum(len(set(r['values'])) > 1 for r in repeated),
                repeated_groups=repeated,
                scope='Raw CPU adapter writes, not SPC packets or NES-equivalence; core frame grouping is not an audio publication boundary')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    with args.trace.open() as stream:
        report = analyze(csv.reader(stream))
    report['trace_sha256'] = hashlib.sha256(args.trace.read_bytes()).hexdigest()
    args.out.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'repeated_groups'}, indent=2))
