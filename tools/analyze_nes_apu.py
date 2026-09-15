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


def matched_frame_timing(events, native, phase):
    """Compare frame spacing only within the unmodified common write prefix.

    NES host frames and SNES raw core frames have different origins. Remove
    one constant origin offset, never a changing offset or an event mismatch.
    This deliberately makes no sub-frame or PCM playback claim.
    """
    prefix = first_difference([(e['address'], e['value']) for e in events],
                              [(0x4000+int(r[5]), int(r[6])) for r in native])['common_prefix_writes']
    indices = [i for i in range(prefix) if events[i]['phase'] == phase]
    if len(indices) < 2:
        raise ValueError('Need at least two matched writes in the selected phase')
    first, last = indices[0], indices[-1]
    offset = int(native[first][1]) - events[first]['frame']
    drift = [int(native[i][1]) - events[i]['frame'] - offset for i in indices]
    return dict(phase=phase, matched_writes=len(indices), first_write_index=first,
                last_write_index=last, common_prefix_writes=prefix,
                unmatched_reference_tail=len(events)-prefix,
                unmatched_candidate_tail=len(native)-prefix,
                origin_offset_frames=offset,
                reference_span_frames=events[last]['frame']-events[first]['frame'],
                candidate_span_frames=int(native[last][1])-int(native[first][1]),
                relative_frame_drift_histogram=dict(sorted(collections.Counter(drift).items())),
                scope='Matched-write frame spacing with one origin offset; not sub-frame jitter, SPC acknowledgement, or PCM fidelity')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace', type=Path)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--snes-bus', type=Path)
    parser.add_argument('--timing-phase', help='Compare common-prefix frame spacing in this NES phase')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.timing_phase and not args.snes_bus:
        parser.error('--timing-phase requires --snes-bus')
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
            rows = list(csv.reader(stream))
        try:
            from .analyze_audio_bus import analyze as analyze_bus
        except ImportError:
            from analyze_audio_bus import analyze as analyze_bus
        bus = analyze_bus(rows)
        writes = [r for r in rows if r[0] == 'W']
        native = [(0x4000+int(r[5]), int(r[6])) for r in writes]
        comparison = first_difference([(r['address'], r['value']) for r in events], native)
        index = comparison['common_prefix_writes']
        if index < len(events):
            comparison['reference_event'] = events[index]
        report['raw_order_comparison'] = comparison
        report['snes_trace_sha256'] = sha(args.snes_bus)
        report['spc_packet_mismatches'] = bus['mismatches']
        if args.timing_phase:
            report['matched_frame_timing'] = matched_frame_timing(events, writes, args.timing_phase)
    args.out.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'events'}, indent=2))
