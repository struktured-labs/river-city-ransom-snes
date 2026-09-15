"""Frame-attributed NES APU write analysis for fresh-process captures."""
import argparse
import collections
import csv
import json
from pathlib import Path

try:
    from .benchmark_report import verify_capture, sha
except ImportError:
    from benchmark_report import verify_capture, sha


def analyze(rows, phases):
    events, counts = [], collections.Counter()
    previous_frame = previous_cycle = -1
    for row in rows:
        if len(row) != 4:
            raise ValueError('Expected host frame, CPU cycle, address, value')
        frame, cycle, address, value = map(int, row)
        if (not 0 <= frame <= len(phases) or frame < previous_frame
                or cycle < previous_cycle or not 0x4000 <= address <= 0x4017
                or not 0 <= value <= 255):
            raise ValueError('Invalid or unordered NES APU trace')
        phase = phases[frame-1] if frame else 'before_first_run'
        counts[phase] += 1
        events.append(dict(frame=frame, cycle=cycle, phase=phase, address=address, value=value))
        previous_frame, previous_cycle = frame, cycle
    if not events:
        raise ValueError('Empty NES APU trace')
    return events, dict(counts)


def first_difference(reference, candidate):
    for index, (a, b) in enumerate(zip(reference, candidate)):
        if a != b:
            return dict(common_prefix_writes=index, reference=a, candidate=b)
    return dict(common_prefix_writes=min(len(reference), len(candidate)),
                reference_length=len(reference), candidate_length=len(candidate))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace', type=Path)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--snes-bus', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    receipt, timeline = verify_capture(args.capture)
    if receipt['system'] != 'nes' or receipt['rom_sha256'] != receipt['templates']['menu']['source_rom']:
        raise ValueError('Expected the original NES reference')
    with args.trace.open() as stream:
        events, phases = analyze(csv.reader(stream), [r['phase'] for r in timeline])
    report = dict(schema='rcr-nes-apu-analysis-v1', writes=len(events), writes_by_phase=phases,
                  trace_sha256=sha(args.trace), capture_sha256=sha(args.capture/'capture.json'),
                  events=events, scope='Raw NES writes and exact host-frame attribution; not a phase-synchronized NES/SNES audio verdict')
    if args.snes_bus:
        with args.snes_bus.open() as stream:
            native = [(0x4000+int(r[5]), int(r[6])) for r in csv.reader(stream) if r[0] == 'W']
        comparison = first_difference([(r['address'], r['value']) for r in events], native)
        index = comparison['common_prefix_writes']
        if index < len(events):
            comparison['reference_event'] = events[index]
        report['raw_order_comparison'] = comparison
        report['snes_trace_sha256'] = sha(args.snes_bus)
    args.out.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'events'}, indent=2))
