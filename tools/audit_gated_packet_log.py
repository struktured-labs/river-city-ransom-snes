"""Join selectively recorded SRAM packets to exact gate events and SPC receipts."""
import argparse
import csv
import json
from pathlib import Path

from tools.audio_packet_log import decode
from tools.audit_audio_packet_log import received_packets
from tools.benchmark_report import sha


def calls(rows):
    if not rows or len(rows) % 2:
        raise ValueError('Missing complete gate/dispatch pairs')
    result = []
    last_clock = -1
    for first, second in zip(rows[::2], rows[1::2]):
        if len(first) != 16 or len(second) != 16:
            raise ValueError('Need exact-clock span schema')
        mode = int(second[0])
        if (first[0] != '0' or mode not in (1, 2) or first[5] != 'c0e600' or
                second[5] != {1: 'c0e080', 2: 'c0d2bc'}[mode] or
                not last_clock < int(first[4]) < int(second[4]) or first[6:] != second[6:]):
            raise ValueError('Wrong gate/dispatch PCs, context or clocks')
        last_clock = int(second[4])
        result.append(dict(packet=len(result), nmi=int(first[6]), frame=int(first[1]),
            clock=int(first[4]), recorded=mode == 1))
    return result


def qualify(log, entries, packets):
    chosen = [r for r in entries if r['recorded']]
    if len(packets) != len(entries) or log['total'] != len(chosen):
        raise ValueError('Receiver/gate/recorded counts disagree')
    for r in log['records']:
        e = chosen[r['sequence']]
        if r['timeout'] or r['nmi'] != e['nmi'] or bytes.fromhex(r['packet']) != packets[e['packet']]:
            raise ValueError('Wrong NMI, timeout or receiver packet for saved record')
    ranges = []
    for entry in entries:
        if not ranges or ranges[-1]['recorded'] != entry['recorded']:
            ranges.append(dict(recorded=entry['recorded'], first=entry, last=entry, count=1))
        else:
            ranges[-1]['last'] = entry
            ranges[-1]['count'] += 1
    return dict(received=len(packets), selected=len(chosen), deliberately_unrecorded=len(entries) - len(chosen),
        retained_matched=len(log['records']), overwritten=log['overwritten'], ranges=ranges)


def audit(candidate, observed, normal, spans, received, out):
    paths = [Path(__file__), Path('tools/audio_packet_log.py'), Path('tools/audit_audio_packet_log.py'),
        spans, received, candidate / 'manifest.json', candidate / 'native-cpu.sfc']
    manifest = json.loads((candidate / 'manifest.json').read_text())
    if sha(candidate / 'native-cpu.sfc') != manifest['rom_sha256']:
        raise ValueError('Candidate differs')
    for p, h in manifest['diagnostic_packet_log']['sources'].items():
        if sha(Path(p)) != h:
            raise ValueError('Build source differs: ' + p)
    for root in (observed, normal):
        r = json.loads((root / 'report.json').read_text())
        if r['status'] != 'passed' or r['rom_sha256'] != manifest['rom_sha256']:
            raise ValueError('Wrong or failed capture')
        for p, h in r['sources'].items():
            if sha(Path(p)) != h:
                raise ValueError('Capture source differs: ' + p)
        paths.append(root / 'report.json')
    neutral = {n: sha(observed / n) == sha(normal / n)
               for n in ('packets.srm', 'frames.json', 'ram.bin', 'last.png', 'audio.wav')}
    if not all(neutral.values()):
        raise ValueError('Observer changed the recorded game')
    with spans.open() as f:
        entries = calls(list(csv.reader(f)))
    with received.open() as f:
        packets = received_packets(csv.reader(f))
    log = decode((observed / 'packets.srm').read_bytes())
    result = qualify(log, entries, packets)
    wrong = list(packets)
    index = next(r['packet'] for r in entries if r['recorded'])
    wrong[index] = bytes([wrong[index][0] ^ 1]) + wrong[index][1:]
    try:
        qualify(log, entries, wrong)
        rejected = False
    except ValueError:
        rejected = True
    if not rejected:
        raise ValueError('Wrong receiver byte survived')
    paths.extend(root / n for root in (observed, normal)
                 for n in ('packets.srm', 'frames.json', 'ram.bin', 'last.png', 'audio.wav'))
    result.update(observer_neutral=neutral, actual_wrong_receiver_mutation_rejected=rejected,
        sources={str(p): sha(p) for p in paths}, deployed=False,
        scope='Exact ordered gate and dispatch events assign each selected record to a global SPC '
              'receipt using sequence and native NMI. Unrecorded intervals are coverage gaps, not lost audio. '
              'No timing-neutrality, physical alignment, skipped-interval payload or speed verdict.')
    out.mkdir(parents=True, exist_ok=False)
    (out / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('received', 'selected', 'deliberately_unrecorded', 'retained_matched', 'ranges')}, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'observed', 'normal', 'spans', 'received', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    audit(**vars(p.parse_args()))
