"""Qualify stored packets against independent SPC receipts; retain observer cost."""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path
import shutil

from tools.audio_packet_log import decode
from tools.benchmark_report import sha


def received_packets(rows):
    packets = []
    pending = []
    for row in rows:
        if len(row) != 3 or int(row[0]) != len(pending) or not 0 <= int(row[1]) <= 255:
            raise ValueError('Incomplete/out-of-order receiver bytes')
        pending.append(int(row[1]))
        if len(pending) == 23:
            packets.append(bytes(pending))
            pending = []
    if pending or not packets:
        raise ValueError('Missing complete receiver packets')
    return packets


def compare(log, received):
    if log['total'] != len(received):
        raise ValueError('CPU/receiver packet counts differ')
    errors = [r['sequence'] for r in log['records'] if r['timeout'] or
              bytes.fromhex(r['packet']) != received[r['sequence']]]
    if errors:
        raise ValueError('CPU/receiver packet mismatch: ' + str(errors[:8]))
    return len(log['records'])


def timing(rows):
    rows = [r for r in rows if int(r[4], 16) >> 16 in (0, 0xC0)]
    costs = Counter()
    excluded = []
    if len(rows) % 2:
        raise ValueError('Unpaired logger timing')
    for a, b in zip(rows[::2], rows[1::2]):
        if a[3] != '0' or b[3] != '1':
            raise ValueError('Missing logger entry/exit')
        # Do not assume 1364 clocks across NTSC's short scanline or frame wrap.
        if a[0] != b[0] or int(b[1]) < int(a[1]) or int(a[1]) <= 240 <= int(b[1]):
            excluded.append([a[:5], b[:5]])
            continue
        cost = (int(b[1]) - int(a[1])) * 1364 + int(b[2]) - int(a[2])
        if cost <= 0:
            raise ValueError('Nonpositive logger duration')
        costs[cost] += 1
    if not costs:
        raise ValueError('No qualified timing samples')
    return dict(master_clock_histogram=dict(sorted(costs.items())), excluded=excluded,
        scope='Elapsed after original SPC sender returns through before logger RTS; '
              'includes refresh/events, excludes added JSR/RTS overhead. Not exclusive instruction cost.')


def audit(candidate, observed, normal, timed, received, events, baseline, out):
    paths = [Path(__file__), Path('tools/audio_packet_log.py'), received, events,
             candidate / 'manifest.json', candidate / 'native-cpu.sfc', baseline.with_suffix('.json'),
             baseline.with_suffix('.ram'), baseline.with_suffix('.png')]
    for directory in (observed, normal, timed):
        report = json.loads((directory / 'report.json').read_text())
        for name, digest in report['sources'].items():
            if sha(Path(name)) != digest:
                raise ValueError('Changed capture source: ' + name)
        paths.extend(directory / n for n in ('report.json', 'packets.srm', 'frames.json',
                                             'ram.bin', 'last.png', 'audio.wav'))
    manifest = json.loads((candidate / 'manifest.json').read_text())
    for name, digest in manifest['diagnostic_packet_log']['sources'].items():
        if sha(Path(name)) != digest:
            raise ValueError('Changed build source: ' + name)
    log = decode((observed / 'packets.srm').read_bytes())
    with received.open() as stream:
        packets = received_packets(csv.reader(stream))
    matched = compare(log, packets)
    negatives = {}
    broken = bytearray((observed / 'packets.srm').read_bytes())
    slot = 1 + log['records'][0]['sequence'] % 4095
    broken[slot * 32 + 7] ^= 1
    try:
        decode(broken)
        negatives['corrupted_saved_byte'] = False
    except ValueError:
        negatives['corrupted_saved_byte'] = True
    wrong = list(packets)
    seq = log['records'][0]['sequence']
    wrong[seq] = bytes([wrong[seq][0] ^ 1]) + wrong[seq][1:]
    try:
        compare(log, wrong)
        negatives['wrong_received_byte'] = False
    except ValueError:
        negatives['wrong_received_byte'] = True
    neutral = {name: len({sha(d / name) for d in (observed, normal, timed)}) == 1
               for name in ('packets.srm', 'frames.json', 'ram.bin', 'last.png', 'audio.wav')}
    with events.open() as stream:
        cost = timing(list(csv.reader(stream)))
    parent = baseline.with_suffix('.ram').read_bytes()
    child = (normal / 'ram.bin').read_bytes()
    difference = [i for i, (a, b) in enumerate(zip(parent, child)) if a != b]
    report = dict(packet_match_passed=True, received_total=len(packets), retained_matched=matched,
        overwritten=log['overwritten'], timeout_records=sum(r['timeout'] for r in log['records']),
        host_observers_neutral=neutral, negative_controls=negatives, timing=cost,
        parent_comparison=dict(final_wram_different_bytes=len(difference), first_offsets=difference[:64],
            final_image_equal=sha(baseline.with_suffix('.png')) == sha(normal / 'last.png')),
        deployed=False, safe_as_timing_neutral_diagnostic=False,
        scope='Executed SRAM wrap and exact retained CPU/SPC bytes. Parent game differs: '
              'not neutral, not approved for Rival, not evidence that physical silences are rests.',
        sources={str(p): sha(p) for p in paths})
    if not all(neutral.values()) or not all(negatives.values()):
        raise ValueError('Observer/negative-control qualification failed')
    out.mkdir(parents=True, exist_ok=False)
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    shutil.copyfile(baseline.with_suffix('.png'), out / 'parent.png')
    shutil.copyfile(normal / 'last.png', out / 'logger.png')
    (out / 'index.html').write_text(f'''<!doctype html><meta charset="utf-8">
<title>Audio packet logger qualification</title>
<style>body{{background:#10151d;color:#eee;font:18px sans-serif;max-width:1000px;margin:2em auto}}
img{{width:384px;image-rendering:pixelated}}figure{{display:inline-block;margin:1em}}</style>
<h1>Sound-command logging: works, but not neutral</h1>
<p>5,000 frames; {len(packets):,} received packets; all {matched:,} retained packets match
the SPC's independently observed bytes. {log['overwritten']} overwritten records are disclosed.</p>
<p>Three emulator observers agree exactly. Corrupted SRAM and wrong receiver-byte controls fail.</p>
<p><strong>Not deployed.</strong> The logger adds work and the parent comparison differs.
This is not a fix for the physical audio gaps, nor a timing-neutral diagnostic.</p>
<figure><img src="parent.png"><figcaption>Unmodified parent, frame5000</figcaption></figure>
<figure><img src="logger.png"><figcaption>Logger diagnostic, same input/frame</figcaption></figure>
<p><a href="report.json">Bound report, measured durations, exclusions and limitations</a></p>''')
    print(json.dumps({k: report[k] for k in ('received_total', 'retained_matched', 'timing', 'parent_comparison')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'observed', 'normal', 'timed', 'received', 'events', 'baseline', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    audit(**vars(parser.parse_args()))
