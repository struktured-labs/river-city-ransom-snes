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
    absolute_timing = None
    if all('absolute_clock' in item for item in completed):
        intervals = [dict(before=a, after=b,
                          master_clocks=b['absolute_clock']-a['absolute_clock'])
                     for a, b in zip(completed, completed[1:])]
        values = [item['master_clocks'] for item in intervals]
        if any(value < 0 for value in values):
            raise ValueError('Absolute completion clock went backwards')
        absolute_timing = dict(
            scope='Actual completion-to-completion clocks; not frame-bin distance or DSP playback timing',
            nominal_ntsc_frame_clocks=357366,
            review_threshold_clocks=536049,
            interval_count=len(values),
            min_master_clocks=min(values) if values else None,
            max_master_clocks=max(values) if values else None,
            mean_master_clocks=sum(values)/len(values) if values else None,
            long_intervals=[item for item in intervals if item['master_clocks'] > 536049])
    return dict(completion_frame_gap_histogram=dict(sorted(gaps.items())),
                absolute_completion_timing=absolute_timing,
                raw_core_frame_gap_histogram=dict(sorted(raw.items())),
                gap_intervals=[dict(before=a, after=b, video_frame_gap=second-first)
                               for a, b, first, second in zip(completed, completed[1:], normalized, normalized[1:])
                               if second-first > 1],
                frame_convention='Pinned SNES9x raw frame + 1 at scanline zero; no sub-frame timing verdict')


def analyze(rows, paired=False, engine_size=None, triple=False):
    if paired and triple:
        raise ValueError('Choose exactly one multi-byte protocol')
    if engine_size is None:
        engine_size = 0x2c1f if paired or triple else 0x2c00
    if engine_size <= 0:
        raise ValueError('Invalid SPC engine size')
    active = False
    transfer_start = None
    transfer_clocks = []
    excluded_transfer_windows = 0
    expected = None
    previous_frame = -1
    completed = []
    clock_width = None
    previous_clock = -1
    for row in rows:
        if len(row) not in (8, 9) or row[0] not in ('S', 'T'):
            raise ValueError('Invalid acknowledgement row')
        if clock_width is not None and clock_width != len(row):
            raise ValueError('Mixed acknowledgement clock formats')
        clock_width = len(row)
        absolute = int(row[8]) if clock_width == 9 else None
        if absolute is not None:
            if absolute < previous_clock:
                raise ValueError('Absolute acknowledgement clock went backwards')
            previous_clock = absolute
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
            if token == 0x7d and y == engine_size + 2:
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
            transfer_start = (frame, line, cycle, absolute)
        else:
            expected_y = min(expected+3, 23) if triple else expected
            if token != expected or y != expected_y:
                raise ValueError('Missing or reordered packet acknowledgement')
            if expected == (21 if triple else 22):
                completed.append(dict(frame=frame, line=line, cycle=cycle, nmi=nmi))
                if absolute is not None:
                    completed[-1]['absolute_clock'] = absolute
                start_frame, start_line, start_cycle, start_absolute = transfer_start
                # Only ordinary active lines: avoid frame-wrap, overscan and
                # short-scanline assumptions in master-clock arithmetic.
                if absolute is not None:
                    transfer_clocks.append(absolute - start_absolute)
                elif frame == start_frame and 0 <= start_line <= line < 224:
                    elapsed = (line-start_line)*1364 + cycle-start_cycle
                    if elapsed < 0:
                        raise ValueError('Acknowledged transfer time went backwards')
                    transfer_clocks.append(elapsed)
                else:
                    excluded_transfer_windows += 1
                expected = None
            else:
                expected += 3 if triple else (2 if paired else 1)
    if not completed or expected is not None:
        raise ValueError('Missing or truncated acknowledged packet stream')
    return dict(schema='rcr-spc-ack-v2', acknowledged_packets=len(completed), paired_transfer=paired,
                triple_transfer=triple,
                data_phase_timing=dict(
                    scope=('Handshake ACK to final byte ACK using accumulated actual scanline clocks, including VBlank and frame wrap; excludes initial ready wait and DSP synthesis'
                           if clock_width == 9 else
                           'Handshake ACK to final byte ACK on ordinary same-frame active scanlines; excludes initial ready wait and DSP synthesis'),
                    measured_packets=len(transfer_clocks), excluded_packets=excluded_transfer_windows,
                    min_master_clocks=min(transfer_clocks) if transfer_clocks else None,
                    max_master_clocks=max(transfer_clocks) if transfer_clocks else None,
                    mean_master_clocks=sum(transfer_clocks)/len(transfer_clocks) if transfer_clocks else None),
                **completion_timing(completed),
                completions=completed,
                scope='CPU observed ready/handshake/all 23 byte echoes; not DSP playback fidelity')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--paired', action='store_true')
    parser.add_argument('--engine-size', type=lambda value: int(value, 0),
                        help='Uploaded SPC byte count; defaults to the selected stock transport')
    args = parser.parse_args()
    with args.trace.open() as stream:
        report = analyze(csv.reader(stream), paired=args.paired, engine_size=args.engine_size)
    report['trace_sha256'] = hashlib.sha256(args.trace.read_bytes()).hexdigest()
    args.out.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'completions'}, indent=2))
