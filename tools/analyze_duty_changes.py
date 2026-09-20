"""Classify pulse duty changes in validated CPU-to-SPC packet traces."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

try:
    from .analyze_audio_bus import analyze
except ImportError:
    from analyze_audio_bus import analyze


def classify(packets):
    events, previous = [], None
    for packet in packets:
        current = bytes.fromhex(packet['bytes'])
        if len(current) != 23:
            raise ValueError('Need complete 23-byte SPC packets')
        if previous is not None:
            for channel, register in enumerate((0, 4)):
                if (current[register] ^ previous[register]) & 192:
                    events.append(dict(frame=packet['frame'], channel=channel,
                        old_duty=previous[register] >> 6, new_duty=current[register] >> 6,
                        enabled=bool(current[21] & (1 << channel)),
                        constant_volume=bool(current[register] & 16),
                        volume_or_envelope_period=current[register] & 15,
                        note_reset=bool(current[22] & (1 << channel)),
                        period_changed=current[register+2:register+4] != previous[register+2:register+4]))
        previous = current
    # Envelope period zero is not silence. Only classify audible candidates
    # from explicit constant-volume controls; retain all other events below.
    active = [e for e in events if e['enabled'] and e['constant_volume']
              and e['volume_or_envelope_period'] > 0]
    return dict(events=events, duty_changes=len(events),
                enabled_constant_volume_changes=len(active),
                enabled_constant_volume_without_note_reset=sum(not e['note_reset'] for e in active),
                scope='Packet-level register evidence, not direct audibility, sub-packet transitions or DSP output')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--length-gate', action='store_true',
                        help='Validate packets after the production length-enable mask')
    args = parser.parse_args()
    with args.trace.open() as stream:
        bus = analyze(csv.reader(stream), length_gate=args.length_gate)
    if bus['mismatches']:
        raise ValueError('Packet contents do not match CPU writes')
    report = classify(bus['packets'])
    report.update(schema='rcr-duty-trace-v1', trace_sha256=hashlib.sha256(args.trace.read_bytes()).hexdigest(),
                  packet_count=bus['packet_count'], length_gate=args.length_gate,
                  gated_packets=len(bus['gated_packets']),
                  unflushed_cpu_writes=bus['unflushed_cpu_writes'])
    args.out.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k != 'events'}, indent=2))
