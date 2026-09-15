"""Analyze opt-in SNES9x NMITIMEN transitions (NTSC, non-interlaced only).

This diagnoses masked VBlank edges, not gameplay speed or audio fidelity.
IPPU.TotalEmulatedFrames advances at line 1, so line 0 belongs after line 261.
"""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path


def analyze(rows):
    spans = []
    disabled = None
    previous = None
    for row in rows:
        frame, line, cycle = map(int, row[:3])
        pc = row[3]
        value, task, depth, bank_guard, ctrl = map(int, row[4:])
        if not 0 <= line < 262 or not 0 <= cycle < 1400:
            raise ValueError('Expected NTSC non-interlaced beam coordinates')
        # Scanline precision is enough for counting masked line-240 edges;
        # cycle is retained in raw evidence, not treated as constant line time.
        position = frame * 262 + (line if line else 262) + cycle / 1400
        if previous is not None and position < previous:
            raise ValueError('Trace is not chronologically ordered')
        previous = position
        event = dict(frame=frame, line=line, cycle=cycle, pc=pc,
                     task=task, depth=depth, bank_guard=bank_guard, ctrl=ctrl)
        if not value & 128:
            if disabled is None:
                disabled = (position, event)
        elif disabled is not None:
            start, origin = disabled
            edges = sum(start < f * 262 + 240 <= position
                        for f in range(origin['frame'], frame + 1))
            spans.append(dict(start=origin, end=event, masked_vblank_edges=edges))
            disabled = None
    by_pc = collections.Counter()
    for span in spans:
        by_pc[span['start']['pc']] += span['masked_vblank_edges']
    return dict(schema='rcr-nmi-mask-analysis-v1', completed_masked_spans=len(spans),
                masked_vblank_edges=sum(by_pc.values()),
                edges_by_disable_pc=dict(sorted(by_pc.items())),
                edge_crossing_spans=[s for s in spans if s['masked_vblank_edges']],
                incomplete_final_span=disabled is not None,
                scope='Masked line-240 edges; not proof of lost game ticks or fidelity')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    with args.trace.open() as stream:
        report = analyze(csv.reader(stream))
    report['trace_sha256'] = hashlib.sha256(args.trace.read_bytes()).hexdigest()
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'edge_crossing_spans'}, indent=2))
