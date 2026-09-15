"""Validate CPU-observed SPC acknowledgements, not DSP synthesis."""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path


def completion_timing(completed):
    # Pinned SNES9x calls S9xStartScreenRefresh at V_Counter == FIRST_VISIBLE_LINE
    # (1); that function increments TotalEmulatedFrames. Scanline zero belongs
    # to the next zero-origin video frame, before that increment has happened.
    normalized = [r['frame'] + (r['line'] == 0) for r in completed]
    gaps = collections.Counter(b-a for a, b in zip(normalized, normalized[1:]))
    if any(gap < 0 for gap in gaps):
        raise ValueError('Completion video frames run backwards')
    raw = collections.Counter(b['frame']-a['frame'] for a, b in zip(completed, completed[1:]))
    return dict(completion_frame_gap_histogram=dict(sorted(gaps.items())),
                raw_core_frame_gap_histogram=dict(sorted(raw.items())),
                gap_intervals=[dict(before=a, after=b, video_frame_gap=second-first)
                               for a, b, first, second in zip(completed, completed[1:], normalized, normalized[1:])
                               if second-first > 1],
                frame_convention='Pinned SNES9x raw frame + 1 at scanline zero; no sub-frame timing verdict')


def analyze(rows):
    active = False
    expected = None
    previous_frame = -1
    completed = []
    for row in rows:
        if len(row) != 8 or row[0] not in ('S', 'T'):
            raise ValueError('Invalid acknowledgement row')
        frame, line, cycle, nmi, token, y = map(int, row[1:7])
        int(row[7], 16)
        if (frame < previous_frame or not 0 <= line < 262 or cycle < 0
                or not 0 <= nmi <= 65535 or not 0 <= token <= 255
                or not 0 <= y <= 65535):
            raise ValueError('Invalid acknowledgement fields/order')
        previous_frame = frame
        if row[0] == 'T':
            raise ValueError(f'SPC acknowledgement timeout at frame {frame}')
        # Firmware upload ends with ready=$7D. Earlier upload tokens are
        # ignored only before that explicit marker with the upload Y value.
        if not active:
            if token == 0x7d and y == 0x2c02:
                active = True
            continue
        if expected is None:
            if token != 0x7d:
                raise ValueError('Missing SPC ready acknowledgement')
            expected = 0xd7
        elif expected == 0xd7:
            if token != 0xd7:
                raise ValueError('Missing packet handshake acknowledgement')
            expected = 0
        else:
            if token != expected or y != expected:
                raise ValueError('Missing or reordered packet acknowledgement')
            if expected == 22:
                completed.append(dict(frame=frame, line=line, cycle=cycle, nmi=nmi))
                expected = None
            else:
                expected += 1
    if not completed or expected is not None:
        raise ValueError('Missing or truncated acknowledged packet stream')
    return dict(schema='rcr-spc-ack-v2', acknowledged_packets=len(completed),
                **completion_timing(completed),
                completions=completed,
                scope='CPU observed ready/handshake/all 23 byte echoes; not DSP playback fidelity')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    with args.trace.open() as stream:
        report = analyze(csv.reader(stream))
    report['trace_sha256'] = hashlib.sha256(args.trace.read_bytes()).hexdigest()
    args.out.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'completions'}, indent=2))
