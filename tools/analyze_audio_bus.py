"""Compare observed CPU APU writes with the bytes offered to the SPC port."""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path


def analyze(rows, length_gate=False):
    latest, pending = {}, collections.defaultdict(list)
    packets, mismatches, overwritten = [], [], []
    packet, flags, writes = [], 0, 0
    enable = None
    eligible = 0
    gated_packets = []
    disabled_reloads, ordering_hazards = [], []
    previous_frame = -1
    for row in rows:
        if len(row) != 8 or row[0] not in ('W', 'P'):
            raise ValueError('Invalid audio bus event')
        kind = row[0]
        frame, line, cycle, nmi, index, value = map(int, row[1:7])
        int(row[7], 16)
        if (frame < previous_frame or not 0 <= line < 262 or cycle < 0
                or not 0 <= nmi <= 65535 or not 0 <= value <= 255
                or not 0 <= index < (24 if kind == 'W' else 23)):
            raise ValueError('Invalid audio bus fields/order')
        previous_frame = frame
        if kind == 'W':
            if packet:
                raise ValueError('CPU APU write interleaved with a packet')
            latest[index] = value
            pending[index].append(value)
            writes += 1
            if index == 21:
                enable = value
                eligible &= value
            if index in (3, 7, 11, 15) and enable is not None:
                eligible |= enable & (1 << (index // 4))
            if index in (3, 7, 11, 15) and enable is not None and not enable & (1 << (index // 4)):
                disabled_reloads.append(dict(frame=frame, register=index, value=value,
                                             channel=index // 4))
            if index in (2, 3):
                flags |= 0x40
            if index in (6, 7):
                flags |= 0x80
            if index in (3, 7, 11, 15):
                flags |= 1 << (index // 4)
            continue
        if index != len(packet):
            raise ValueError('Missing or reordered packet byte')
        packet.append(value)
        if len(packet) != 23:
            continue
        for register, expected in latest.items():
            if register == 21 and length_gate:
                expected &= eligible | 0xF0
            if register < 22 and packet[register] != expected:
                mismatches.append(dict(frame=frame, register=register, expected=expected,
                                       observed=packet[register]))
        # Initial packet flags may include bootstrap state not observed as a
        # game write. Every subsequent packet follows a traced publication.
        if packets and packet[22] != flags:
            mismatches.append(dict(frame=frame, register=22, expected=flags, observed=packet[22]))
        for register, values in pending.items():
            if register < 22 and len(set(values)) > 1:
                overwritten.append(dict(packet=len(packets), frame=frame,
                                        register=register, values=values))
        packets.append(dict(frame=frame, nmi=nmi, bytes=bytes(packet).hex(),
                            cpu_writes=sum(map(len, pending.values()))))
        if length_gate and enable is not None and (enable & (eligible | 0xF0)) != enable:
            gated_packets.append(dict(packet=len(packets)-1, frame=frame,
                                      raw_enable=enable, eligible=eligible,
                                      expected_enable=enable & (eligible | 0xF0), observed_enable=packet[21]))
        for event in disabled_reloads:
            if packet[21] & (1 << event['channel']):
                ordering_hazards.append(dict(**event, packet=len(packets)-1,
                                             publication_frame=frame,
                                             final_enable=packet[21], final_flags=packet[22]))
        disabled_reloads = []
        packet, flags, pending = [], 0, collections.defaultdict(list)
    if not packets:
        raise ValueError('No complete SPC packet observed')
    if packet:
        raise ValueError('Truncated final SPC packet')
    return dict(schema='rcr-audio-bus-analysis-v1', cpu_writes=writes,
                length_gate=length_gate, gated_packets=gated_packets,
                packet_count=len(packets), mismatches=mismatches,
                changing_register_groups_between_packets=overwritten,
                disabled_reload_then_enabled_in_packet=ordering_hazards,
                unflushed_cpu_writes=sum(map(len, pending.values())), packets=packets,
                scope='Bytes offered to SPC port versus last CPU writes and accumulated event flags; not ACK completion, playback, or NES fidelity')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--length-gate', action='store_true', help='Validate enable bits using ordered disable/reload eligibility')
    args = parser.parse_args()
    with args.trace.open() as stream:
        result = analyze(csv.reader(stream), length_gate=args.length_gate)
    result['trace_sha256'] = hashlib.sha256(args.trace.read_bytes()).hexdigest()
    args.out.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('packets', 'changing_register_groups_between_packets')}, indent=2))
    raise SystemExit(1 if result['mismatches'] else 0)
