"""Cross-check the older even-byte observer against a complete replay trace.

Never reconstruct missing bus bytes. The full trace is independently captured;
every timeline row and PCM byte must match both the older observer and normal
core. Key-on fields are cross-checked against actual received packet bytes.
"""
import argparse
import csv
import json
from pathlib import Path

from tools.analyze_audio_bus import analyze as analyze_bus
from tools.analyze_game_keyons import analyze as analyze_keyons
from tools.benchmark_report import sha, verify_capture


def compare_streams(partial, full, keyons):
    projection = [row for row in full if row[0] == 'W' or int(row[5]) % 2 == 0]
    if not partial or partial != projection:
        raise ValueError('Old trace does not exactly match the even-byte projection')
    bus = analyze_bus(iter(full), length_gate=True)
    if bus['mismatches'] or bus['unflushed_cpu_writes']:
        raise ValueError('Incomplete or mismatching CPU/SPC transport')
    schedule = analyze_keyons(iter(keyons), fast=True)
    if not schedule['passed']:
        raise ValueError('Incorrect key-on schedule')
    headers = [row for row in keyons if row[0] == 'P']
    if len(headers) != len(bus['packets']):
        raise ValueError('Key-on packet count differs')
    for number, (header, packet) in enumerate(zip(headers, bus['packets']), 1):
        data = bytes.fromhex(packet['bytes'])
        # SPC packet destination $40..$56: reset=$56, enable=$55,
        # pulse controls=$40/$44. No masking or synthesized odd bytes.
        if (int(header[1]) != number or list(map(int, header[2:6])) !=
                [data[22], data[21], data[0], data[4]]):
            raise ValueError('Key-on fields differ from full bus packet')
    return dict(packets=len(headers), partial_rows=len(partial), full_rows=len(full),
                keyon_schedule=schedule)


def audit(observer, full_capture, normal, partial_bus, full_bus, keyons, out):
    captures = [verify_capture(root) for root in (observer, full_capture, normal)]
    baseline, rows = captures[-1]
    for receipt, timeline in captures:
        if (receipt['system'] != 'snes' or not receipt['capture_complete']
                or any(row['fault'] for row in timeline) or timeline != rows
                or any(receipt[key] != baseline[key] for key in
                       ('rom_sha256', 'scenario', 'audio_sha256'))):
            raise ValueError('Capture not complete, fault-free and observer-neutral')
    for (receipt, _), path in zip(captures, (partial_bus, full_bus)):
        if receipt.get('audio_bus_trace', {}).get('sha256') != sha(path):
            raise ValueError('Bus trace is not capture-bound')
    def read(path):
        with path.open() as source:
            return list(csv.reader(source))
    result = dict(schema='rcr-keyon-provenance-v1', passed=True,
                  frames=len(rows), rom_sha256=baseline['rom_sha256'],
                  audio_sha256=baseline['audio_sha256'],
                  **compare_streams(read(partial_bus), read(full_bus), read(keyons)),
                  scope='Exact replay neutrality, old even-byte trace projection, '
                        'and all key-on packet fields/schedules. Key-on trace is '
                        'cross-correlated after capture, not a contemporaneous '
                        'receipt binding. Not DSP sample timing or analog fidelity.',
                  sources={str(path): sha(path) for path in
                           (observer/'capture.json', full_capture/'capture.json',
                            normal/'capture.json', partial_bus, full_bus, keyons)})
    out.mkdir(parents=True, exist_ok=False)
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('observer', 'full-capture', 'normal', 'partial-bus', 'full-bus', 'keyons', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    result = audit(**vars(parser.parse_args()))
    print(json.dumps({key: result[key] for key in ('passed', 'frames', 'packets')}))
