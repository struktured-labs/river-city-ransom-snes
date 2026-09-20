"""Validate reset/duty-derived pulse key-ons from the deferred SPC experiment."""
import argparse
import csv
import hashlib
import json
from pathlib import Path


def analyze(rows, *, triple=False, fast=False, splash_ident=False, receiver_pc=None):
    if receiver_pc is None:receiver_pc=0x300c if triple else 0x3008
    packet = 0
    old_duty = [0, 0]
    pending = None
    expected = []
    observed = []
    events = []
    startup = []

    def finish_packet():
        nonlocal pending
        if pending is None:
            return
        wanted = events[-1]['expected_keyons']
        if observed != wanted:
            events[-1]['observed_keyons'] = list(observed)
        pending = None
        observed.clear()

    for row in rows:
        if not row:
            raise ValueError('Empty key-on row')
        if row[0] == 'P':
            if len(row) != 7:
                raise ValueError('Malformed packet row')
            finish_packet()
            number, reset, enable, control0, control1 = map(int, row[1:6])
            pc = int(row[6], 16)
            if number != packet + 1 or pc != receiver_pc or any(
                    not 0 <= value <= 255 for value in (reset, enable, control0, control1)):
                raise ValueError('Invalid packet order, value or receiver PC')
            packet = number
            reset_bits = reset & enable & 3
            duty_bits = 0
            for channel, control in enumerate((control0, control1)):
                bit = 1 << channel
                if enable & bit:
                    duty = control >> 6
                    if duty != old_duty[channel]:
                        duty_bits |= bit
                    old_duty[channel] = duty
            pending = reset_bits | duty_bits
            expected_keyons = ([pending] if pending else [])
            if fast and not reset_bits:
                expected_keyons = [bit for bit in (1, 2) if duty_bits & bit]
            expected.append(expected_keyons)
            events.append(dict(packet=packet, reset=reset, enable=enable,
                               control=[control0, control1], reset_bits=reset_bits,
                               duty_bits=duty_bits, expected_keyon=pending,
                               expected_keyons=expected_keyons))
        elif row[0] == 'K':
            if len(row) != 4:
                raise ValueError('Malformed key-on row')
            number, value, pc = int(row[1]), int(row[2]), int(row[3], 16)
            if not 0 <= value <= 255:
                raise ValueError('Invalid key-on value')
            if number == 0:
                if packet or pending is not None:
                    raise ValueError('Late startup key-on')
                startup.append((value, pc))
            else:
                expected_pc = (0x3062 if events[-1]['reset_bits'] else
                               0x3072 if value == 1 else 0x307d) if fast else 0x3035
                if number != packet or pending is None or pc != expected_pc:
                    raise ValueError('Out-of-order or wrong-site gameplay key-on')
                observed.append(value)
        else:
            raise ValueError('Unknown key-on event')
    finish_packet()
    expected_startup = ([(3, 0x033b)] if splash_ident else []) + [(0, 0x0bcb), (15, 0x0456)]
    if not packet or startup != expected_startup:
        raise ValueError('Missing packets or unexpected startup key-ons')
    mismatches = [event for event in events if
                  event.get('observed_keyons', event['expected_keyons']) != event['expected_keyons']]
    reset_only = sum(bool(e['reset_bits']) and not e['duty_bits'] for e in events)
    duty_only = sum(bool(e['duty_bits']) and not e['reset_bits'] for e in events)
    merged = sum(bool(e['reset_bits']) and bool(e['duty_bits']) for e in events)
    both_voices = sum(e['expected_keyon'] == 3 for e in events)
    keyons = sum(map(len, expected))
    return dict(schema='rcr-game-keyon-audit-v1', passed=not mismatches,
                startup_keyons=startup, splash_ident=splash_ident,
                packets=packet, expected_keyon_writes=keyons,
                reset_only_packets=reset_only, duty_only_packets=duty_only,
                merged_reset_duty_packets=merged, both_voice_packets=both_voices,
                mismatch_count=len(mismatches), mismatches=mismatches,
                transport='triple' if triple else 'paired',
                schedule='fast' if fast else 'deferred',
                scope='Deferred pulse KON schedule from reset, enable and duty state; not DSP phase, PCM fidelity or click detection')


def audit(trace, out, *, triple=False, fast=False):
    with trace.open() as source:
        report = analyze(csv.reader(source), triple=triple, fast=fast)
    report['trace_sha256'] = hashlib.sha256(trace.read_bytes()).hexdigest()
    out.write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--triple', action='store_true')
    parser.add_argument('--fast', action='store_true')
    args = parser.parse_args()
    result = audit(args.trace, args.out, triple=args.triple, fast=args.fast)
    print(json.dumps({k:v for k,v in result.items() if k != 'mismatches'}, indent=2))
    raise SystemExit(0 if result['passed'] else 1)
