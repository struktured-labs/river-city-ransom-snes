"""Measure original camera-calculation cadence without equating motion to speed."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import statistics

from tools.audit_park_spans import parse as parse_spans
from tools.benchmark_report import sha, verify_capture


def parse_nes(records, first, last):
    result = []
    previous = None
    for row in records:
        if len(row) != 6:
            raise ValueError('Need six-column NES CPU-write trace')
        frame, line, clock = map(int, row[:3])
        pc, address = (int(x, 16) for x in row[3:5])
        value = int(row[5])
        if (not first <= frame <= last or clock < 0 or not 0 <= value <= 255
            or (previous is not None and (clock <= previous[1] or frame < previous[0]))):
            raise ValueError('Invalid or nonmonotonic NES camera trace')
        previous = frame, clock
        if pc == 0xe2b1 and address == 0xf6:
            result.append(dict(frame=frame, line=line, clock=clock))
    if not result:
        raise ValueError('No original camera commits')
    return result


def active(row, phase):
    ram = bytes.fromhex(row['game_ram_hex'])
    if len(ram) != 2048:
        raise ValueError('Need full original RAM')
    return (row['phase'] == phase and ram[0x42] == 3 and ram[0x100] & 192 == 192
            and not ram[0x107] & 128 and not ram[0x3f] & 32
            and not row.get('native', {}).get('transition_state', 0))


def measure(events, rows, phase, clocks_per_frame):
    intervals = []
    excluded = 0
    for a, b in zip(events, events[1:]):
        if not 1 <= a['frame'] <= b['frame'] <= len(rows) or b['clock'] <= a['clock']:
            raise ValueError('Invalid camera interval')
        window = rows[a['frame']-1:b['frame']]
        if not all(active(row, phase) for row in window):
            excluded += 1
            continue
        elapsed = b['clock'] - a['clock']
        intervals.append(dict(start=a, end=b, clocks=elapsed,
                              nominal_frames=elapsed/clocks_per_frame))
    if len(intervals) < 100:
        raise ValueError('Insufficient active traversal cadence coverage')
    values = [s['nominal_frames'] for s in intervals]
    return dict(intervals=intervals, excluded_intervals=excluded,
        count=len(values), minimum=min(values), mean=statistics.mean(values),
        maximum=max(values), standard_deviation=statistics.pstdev(values),
        frame_number_gaps=dict(Counter(s['end']['frame']-s['start']['frame'] for s in intervals)))


def load(capture, normal, system):
    receipt, rows = verify_capture(capture)
    baseline, reference = verify_capture(normal)
    if (receipt['system'] != system or not receipt['capture_complete'] or rows != reference
        or any(receipt[k] != baseline[k] for k in ('rom_sha256', 'scenario_sha256', 'audio_sha256', 'frames'))):
        raise ValueError('Incomplete/nonneutral cadence replay')
    key = 'nes_scroll_trace' if system == 'nes' else 'span_trace'
    binding = receipt[key]
    trace = Path(binding['path'])
    if (sha(trace) != binding['sha256'] or binding['first'] > 1
        or binding['last'] < len(rows)):
        raise ValueError('Incomplete or unbound cadence trace')
    with trace.open() as stream:
        if system == 'nes':
            if binding['observer_sha256'] != sha(Path('.deps/fceumm/src/x6502.c')):
                raise ValueError('NES observer source changed')
            events = parse_nes(csv.reader(stream), binding['first'], binding['last'])
        else:
            metadata = json.loads((capture/'span-points.json').read_text())
            for path, digest in metadata['sources'].items():
                if sha(Path(path)) != digest:
                    raise ValueError('Span definition source changed')
            point, = [p for p in metadata['points'] if p['index'] == 8]
            if point['label'] != 'camera_exit' or binding['points']['8'] != point['pc']:
                raise ValueError('Wrong camera timing point')
            events = [{k: r[k] for k in ('frame', 'line', 'clock')}
                      for r in parse_spans(csv.reader(stream), binding) if r['event'] == 8]
    return receipt, rows, events, trace


def audit(nes, snes, normal_nes, normal_snes, out):
    data = [load(capture, normal, system) for system, capture, normal in
            (('nes', nes, normal_nes), ('snes', snes, normal_snes))]
    if data[0][0]['scenario_sha256'] != data[1][0]['scenario_sha256']:
        raise ValueError('Different traversal policies')
    phases = ('park_00_east_sweep', 'park_00_west_sweep')
    results = {system: {phase: measure(events, rows, phase, clock) for phase in phases}
               for system, (_, rows, events, _), clock in zip(('nes', 'snes'), data, (29780.5, 357366))}
    paths = [Path(__file__), Path('tools/benchmark_capture.py'), Path('tools/benchmark_report.py'),
             Path('tools/audit_park_spans.py'), Path('tools/snes9x_span_trace.inc'),
             Path('.deps/fceumm/src/x6502.c'), *[d[3] for d in data],
             snes/'span-points.json',
             *[p/'capture.json' for p in (nes, snes, normal_nes, normal_snes)]]
    report = dict(observer_neutral=True, release_ready=False, results=results,
        sources={str(p): sha(p) for p in paths},
        scope='Every adjacent camera-calculation interval wholly within each active park sweep. '
              'NES CPU write E2B1/F6 versus SNES translated camera-tail entry (constant pre-store offset). '
              'NTSC nominal clocks/frame: NES29780.5 CPU, SNES357366 master. No favorable subset or '
              'image alignment. Different encounters and walking/knockback states remain possible; '
              'counts and update jitter do not certify matched combat speed or acoustic tempo. '
              'Full normal-core timelines and PCM must match each observer separately.')
    out.mkdir(parents=True, exist_ok=False)
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({s: {p: {k: v for k, v in r.items() if k != 'intervals'}
                          for p, r in phases.items()} for s, phases in results.items()}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('nes', 'snes', 'normal-nes', 'normal-snes', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    audit(**vars(parser.parse_args()))
