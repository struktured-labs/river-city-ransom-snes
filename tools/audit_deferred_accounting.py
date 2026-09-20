"""Check retained-NMI accounting at every captured frame boundary."""
import argparse
import json
from pathlib import Path

from tools.benchmark_report import sha, verify_capture


def analyze(rows):
    previous = None
    scheduled = served = 0
    for row in rows:
        n = row['native']
        a, b, pending, fallback = (n['deferred_game_nmi_'+key] for key in
                                   ('scheduled', 'served', 'pending', 'fallback'))
        if any(type(v) is not int or not 0 <= v <= 65535 for v in (a, b, fallback)) or pending not in (0, 1):
            raise ValueError('Invalid retained-NMI counters')
        if ((a-b) & 65535) != pending or fallback:
            raise ValueError('Lost/duplicate retained job or fallback observed')
        if previous is not None:
            frame, pa, pb = previous
            if row['frame'] != frame+1:
                raise ValueError('Nonconsecutive frame accounting')
            da, db = (a-pa) & 65535, (b-pb) & 65535
            if da > 1 or db > 1:
                raise ValueError('Multiple retained jobs in one output frame')
            scheduled += da
            served += db
        previous = row['frame'], a, b
    if previous is None or not scheduled or rows[-1]['native']['deferred_game_nmi_pending']:
        raise ValueError('Missing complete retained-work coverage')
    return dict(frames=len(rows), scheduled_advances=scheduled, served_advances=served,
                final_scheduled=previous[1], final_served=previous[2], fallback_count=0)


def audit(captures, out):
    results = {}
    roms = set()
    for path in captures:
        receipt, rows = verify_capture(path)
        if not receipt['capture_complete'] or receipt['system'] != 'snes' or any(r['fault'] for r in rows):
            raise ValueError('Incomplete or faulted SNES capture')
        roms.add(receipt['rom_sha256'])
        results[str(path)] = analyze(rows)
    if len(roms) != 1:
        raise ValueError('Mixed retained-scheduler cartridges')
    report = dict(passed=True, rom_sha256=roms.pop(), captures=results,
        sources={str(p): sha(p) for p in [Path(__file__), Path('tools/benchmark_report.py'),
                                        *[p/'capture.json' for p in captures]]},
        scope='Every sampled frame boundary: scheduled-minus-served equals pending, '
              'zero fallback, no multi-job advances, no final pending work. Modular16-bit '
              'counters; not instruction-by-instruction atomicity or independent proof '
              'that the original body executed. Real-edge fixtures and received-audio '
              'traces remain separate checks.')
    out.mkdir(parents=True, exist_ok=False)
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--captures', nargs='+', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    audit(**vars(p.parse_args()))
