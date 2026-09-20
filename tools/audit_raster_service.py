"""Fail experimental raster captures with lost jobs or missed arm deadlines."""
import argparse
import hashlib
import json
from pathlib import Path
import struct


def counters(memory):
    scheduled, overwritten, served, late = struct.unpack_from('<4H', memory, 0x1CA8)
    pending = memory[0x1CA3]
    rearms = struct.unpack_from('<H', memory, 0x1CB8)[0]
    return dict(scheduled=scheduled, overwritten=overwritten, served=served,
                late=late, rearms=rearms, pending=pending,
                balanced=scheduled == served + overwritten + pending,
                passed=bool(scheduled) and overwritten == 0 and late == 0 and rearms == 0
                and pending <= 1 and scheduled == served + pending)


def audit(capture, out):
    out.mkdir(parents=True, exist_ok=False)
    timeline = json.loads((capture/'timeline.json').read_text())
    if len(timeline) >= 65536:
        raise ValueError('16-bit counter audit requires a capture shorter than 65536 frames')
    phases = dict.fromkeys(row['phase'] for row in timeline)
    rows = []
    for phase in phases:
        path = capture/(phase+'.ram')
        memory = path.read_bytes()
        row = dict(phase=phase, **counters(memory), ram_sha256=hashlib.sha256(memory).hexdigest())
        rows.append(row)
    exercised = [row for row in rows if row['scheduled']]
    report = dict(scope='Experimental raster accounting and arm deadlines, not audio fidelity',
                  capture=str(capture), phases=rows,
                  passed=bool(exercised) and all(row['passed'] for row in exercised))
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))
    return report['passed']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if audit(args.capture, args.out) else 1)
