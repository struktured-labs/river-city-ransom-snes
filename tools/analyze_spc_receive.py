"""Compare CPU packet data with bytes actually consumed by the SPC receiver."""
import argparse
import csv
import hashlib
import json
from pathlib import Path


def length_usage(packets):
    channels = [dict(channel=name, enabled_halted=0, enabled_running=0, disabled=0)
                for name in ('pulse1', 'pulse2', 'triangle', 'noise')]
    running = []
    for number, packet in enumerate(packets):
        if len(packet) != 23:
            raise ValueError('Need complete received packets')
        for i, (register, halt) in enumerate(((0, 32), (4, 32), (8, 128), (12, 32))):
            state = ('disabled' if not packet[21] & (1 << i) else
                     'enabled_halted' if packet[register] & halt else 'enabled_running')
            channels[i][state] += 1
            if state == 'enabled_running':
                running.append(dict(packet=number, channel=i, control=packet[register],
                                    length_index=packet[register + 3] >> 3))
    return dict(channels=channels, enabled_running_events=running,
                scope='Received enable/halt bits only, not actual counter values or sub-packet transitions')


def compare(sent_rows, received_rows, paired=False, triple=False, receiver_pcs=None):
    if paired and triple:
        raise ValueError('Choose exactly one multi-byte protocol')
    if receiver_pcs is not None and (not paired or triple or len(receiver_pcs)!=2
            or len(set(receiver_pcs))!=2 or any(not 0x400<=pc<0xffc0 for pc in receiver_pcs)):
        raise ValueError('Relocated receiver requires two checked paired store PCs')
    sent = []
    for row in sent_rows:
        if len(row) != 8 or row[0] not in ('W', 'P'):
            raise ValueError('Malformed CPU bus record')
        if row[0] == 'P':
            index, value = map(int, row[5:7])
            if index != len(sent) % 23 or not 0 <= value <= 255:
                raise ValueError('Invalid CPU packet sequence/value')
            sent.append((index, value, int(row[1])))
    received = []
    physical = 0
    for row in received_rows:
        if len(row) != 3:
            raise ValueError('Malformed SPC receive record')
        index, value = map(int, row[:2])
        expected_index = physical % 24 if triple else len(received) % 23
        expected_pc = (0x3008 + 4*(expected_index % 3)) if triple else (
            (0x3011 if index & 1 else 0x3008) if paired else 0x48F)
        if receiver_pcs is not None:expected_pc=receiver_pcs[index&1]
        if index != expected_index or not 0 <= value <= 255 or int(row[2], 16) != expected_pc:
            raise ValueError('Invalid pinned SPC receiver sequence/value/PC')
        physical += 1
        if triple and index == 23:
            if value != 0:
                raise ValueError('Nonzero triple padding byte')
            continue
        received.append((index, value))
    if not sent or len(sent) % 23 or len(received) != len(sent) or (triple and physical % 24):
        raise ValueError('Empty, incomplete or unequal packet streams')
    mismatches = [dict(packet=i // 23, index=a[0], sent=a[1], received=b[1], cpu_frame=a[2])
                  for i, (a, b) in enumerate(zip(sent, received)) if a[1] != b[1]]
    return dict(schema='rcr-spc-receiver-audit-v1', passed=not mismatches, paired_transfer=paired,
                triple_transfer=triple, physical_stores=physical,
                packets=len(sent) // 23, bytes_compared=len(sent),
                length_usage=length_usage([bytes(v for _, v in received[i:i+23])
                                           for i in range(0, len(received), 23)]),
                mismatch_count=len(mismatches), mismatches=mismatches,
                scope='Ordered CPU data versus actual pinned SPC receive stores; not perceptual audio fidelity')


def audit(bus, received, out, paired=False):
    with bus.open() as a, received.open() as b:
        report = compare(csv.reader(a), csv.reader(b), paired)
    report['bus_sha256'] = hashlib.sha256(bus.read_bytes()).hexdigest()
    report['receive_sha256'] = hashlib.sha256(received.read_bytes()).hexdigest()
    out.write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('bus', 'received', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--paired', action='store_true')
    args = p.parse_args()
    result = audit(args.bus, args.received, args.out, paired=args.paired)
    print(json.dumps({k: v for k, v in result.items() if k != 'mismatches'}))
    raise SystemExit(0 if result['passed'] else 1)
