"""Separate SRAM mapping, initial contents, initialization execution and recording."""
import argparse
import html
import json
from pathlib import Path

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha, verify_capture


def audit(out):
    base = Path('build/balanced-pitch-game-normal-1494')
    reference, baseline = verify_capture(base)
    specs = (
        ('Mapping only', 'audio-packet-mapping-control-game-1597', 'audio-packet-mapping-control-entry-1600', None),
        ('Boot initializer only', 'audio-packet-boot-control-game-1595', 'audio-packet-boot-control-entry-1599', None),
        ('Splash initializer only', 'audio-packet-splash-control-game-1607', 'audio-packet-splash-control-entry-1610', None),
        ('Preloaded SRAM, no logging', 'audio-packet-seeded-control-game-1612', 'audio-packet-seeded-control-entry-1617', 'audio-packet-seeded-control-1612.json'),
        ('Boot initializer + gameplay gate', 'audio-packet-gated-game-1591', 'audio-packet-gated-entry-1593', None),
        ('Splash initializer + gameplay gate', 'audio-packet-splash-gated-game-1602', 'audio-packet-splash-gated-entry-1608', None),
        ('Preloaded SRAM + gameplay gate', 'audio-packet-seeded-gated-game-1614', 'audio-packet-seeded-gated-entry-1620', 'audio-packet-seeded-gated-1614.json'),
        ('Preloaded SRAM + continuous logger', 'audio-packet-seeded-continuous-game-1619', 'audio-packet-seeded-continuous-entry-1622', 'audio-packet-seeded-continuous-1619.json'))
    paths = [Path(__file__), Path('tools/benchmark_report.py'), Path('tools/audit_room_entry.py'), base / 'capture.json']
    results = []
    for name, game_name, entry_name, seed_name in specs:
        game, entry = Path('build') / game_name, Path('build') / entry_name
        receipt, rows = verify_capture(game)
        e = json.loads((entry / 'report.json').read_text())
        if (not receipt['capture_complete'] or e['audit_sha256'] != sha(Path('tools/audit_room_entry.py')) or
                e['sources']['snes']['capture_sha256'] != sha(game / 'capture.json')):
            raise ValueError('Wrong entry/capture binding')
        if seed_name:
            seed_path = Path('build') / seed_name
            seed = bound_report(seed_path)
            if (len(seed['loaded']) != 1 or seed['loaded'][0]['rom_sha256'] != receipt['rom_sha256'] or
                    seed['loaded'][0]['core_sha256'] != receipt['core_sha256'] or
                    seed['command'][seed['command'].index('--out') + 1] != str(game)):
                raise ValueError('Seed receipt does not belong to capture')
            paths.append(seed_path)
        results.append(dict(name=name, frames=receipt['frames'], parent_timeline_equal=rows == baseline,
            parent_audio_equal=receipt['audio_sha256'] == reference['audio_sha256'],
            room_entry_passed=e['passed'], gates=e['gates'], link=entry_name,
            first_visible=[c['snes']['first_nonblack_offset'] for c in e['comparisons']]))
        paths.extend((game / 'capture.json', entry / 'report.json'))
    coverage = []
    for name in ('audio-packet-gated-coverage-1598', 'audio-packet-splash-gated-coverage-1609',
                 'audio-packet-seeded-gated-coverage-1621'):
        p = Path('build') / name / 'report.json'
        c = bound_report(p)
        coverage.append(dict(name=name, **{k: c[k] for k in ('received', 'selected',
            'deliberately_unrecorded', 'retained_matched', 'ranges')}))
        paths.append(p)
    # Bind explicit seeding for both halves of the last selective comparison.
    for name in ('audio-packet-seeded-gated-1615.json', 'audio-packet-seeded-gated-1616.json'):
        p = Path('build') / name
        bound_report(p)
        paths.append(p)
    report = dict(controls=results, coverage=coverage, deployed=False,
        sources={str(p): sha(p) for p in paths},
        scope='Input-policy replays with exact parent timeline/PCM comparisons and unchanged NES '
              'room-entry gates. Controls separate mapping/initial contents from executed initialization; '
              'do not attribute every later gameplay difference to one cause. No physical audio verdict.')
    out.mkdir(parents=True, exist_ok=False)
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    table = ''.join('<tr><td>' + html.escape(r['name']) + '</td>' + ''.join(
        '<td>' + html.escape(str(r[k])) + '</td>' for k in ('frames', 'parent_timeline_equal',
            'parent_audio_equal', 'first_visible', 'room_entry_passed')) + '</tr>' for r in results)
    links = ''.join(f'<li><a href="../{r["link"]}/">{html.escape(r["name"])}: complete fade collages</a></li>' for r in results)
    (out / 'index.html').write_text('''<!doctype html><meta charset="utf-8">
<title>Sound logger initialization controls</title>
<style>body{background:#10151d;color:#eee;font:18px system-ui;max-width:1200px;margin:2em auto}
td,th{padding:.5em;border:1px solid #64748b}table{border-collapse:collapse}a{color:#7dd3fc}</style>
<h1>Reliable packets do not establish neutral instrumentation</h1>
<p>Mapping SRAM and preloading an empty header preserve the complete parent timeline and PCM.
Executing initialization alone can reproduce the fade failure, without logging any game packet.
The gated and continuous recording paths still fail after removing that initialization.</p>
<table><tr><th>Control</th><th>Frames</th><th>Exact parent timeline</th><th>Exact parent PCM</th>
<th>First visible offsets (NES 7/7/7)</th><th>All entry gates pass</th></tr>''' + table + '''</table>
<p>The preloaded gameplay gate records3,137 packets, all exactly matched to independent SPC receipts
using actual dispatch events and native NMI numbers. It deliberately omits1,461 packets, including
a29-packet interior interval. These are explicit coverage gaps, not lost-audio claims.</p>
<p><strong>No new hardware build deployed. Physical audio artifacts remain unresolved.</strong>
Seeded SRAM is an emulator setup here; MiSTer seed loading has not been verified.</p><ul>''' + links +
        '</ul><p><a href="report.json">Bound reports and full coverage ranges</a></p>')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    audit(**vars(p.parse_args()))
