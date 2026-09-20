"""Detect stale displayed camera across unchanged committed-frame boundaries."""
import argparse
import csv
import json
from pathlib import Path

from tools.audit_scroll_splits import eligible, neutral, scan
from tools.benchmark_report import sha


def held(rows, rendered):
    checks, failures = [], []
    for previous, current in zip(rows, rows[1:]):
        if not eligible(previous) or not eligible(current):
            continue
        if current['frame'] != previous['frame']+1:
            raise ValueError('Nonconsecutive camera observations')
        a, b = (bytes.fromhex(r['game_ram_hex']) for r in (previous, current))
        if len(a) != 2048 or len(b) != 2048:
            raise ValueError('Missing original RAM')
        ca, cb = (r[0xf6] | ((r[0x3d] & 1) << 8) for r in (a, b))
        if a[0x42] != b[0x42] or ca != cb:
            continue
        frame = current['frame']
        lines = rendered.get(frame, {})
        if set(lines) != set(range(32, 192)):
            raise ValueError('Incomplete camera renderer observation')
        row = dict(frame=frame, room=b[0x42], committed=cb,
                   actual_values=sorted(set(lines.values())))
        checks.append(row)
        if row['actual_values'] != [cb]:
            failures.append(row)
    if not checks:
        raise ValueError('No unchanged-camera coverage')
    return dict(checked_frames=len(checks), checks=checks, failures=failures)


def analyze(capture, normal):
    rows, trace = neutral(capture, normal)
    frames = [r['frame'] for p, r in zip(rows, rows[1:]) if eligible(p) and eligible(r)]
    with trace.open() as stream:
        rendered = scan(csv.DictReader(stream), frames)
    result = held(rows, rendered)
    result['sources'] = {str(p): sha(p) for p in (capture/'capture.json', normal/'capture.json', trace)}
    return result


def audit(capture, normal, negative, negative_normal, out):
    good, bad = analyze(capture, normal), analyze(negative, negative_normal)
    if not bad['failures']:
        raise ValueError('Known extra-frame hold was not detected')
    report = dict(passed=not good['failures'], release_ready=False, candidate=good, negative=bad,
        sources={str(p): sha(p) for p in (Path(__file__), Path('tools/audit_scroll_splits.py'))},
        scope='All active same-room frames with equal committed camera at consecutive '
              'frame boundaries; all160 actual rendered street lines required. Detects '
              'an extra-frame retained camera, not camera calculated after scanout, '
              'all intra-frame transitions, simulation speed or acoustics. Existing '
              'end-of-frame warning and settling reports are unchanged.')
    out.mkdir(parents=True, exist_ok=False)
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'], checked=good['checked_frames'],
                         failures=len(good['failures']), negative_failures=bad['failures'])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('capture', 'normal', 'negative', 'negative-normal', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    audit(**vars(parser.parse_args()))
