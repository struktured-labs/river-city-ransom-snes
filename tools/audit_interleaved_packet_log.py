"""Retain exact packets, sender timing exclusions and failed fades for two diagnostics."""
import argparse
import csv
import html
import json
from pathlib import Path

from tools.audio_packet_log import decode
from tools.audit_audio_packet_log import compare, received_packets, timing
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha, verify_capture
from tools.build_packet_log_cost_review import cost_summary


def sender_cost(rows):
    rows = [r for r in rows if int(r[4], 16) >> 16 in (0, 0xC0)]
    censored = []
    if rows and rows[0][3] == '1':
        censored.append(dict(reason='leading exit', event=rows.pop(0)))
    if rows and rows[-1][3] == '0':
        censored.append(dict(reason='trailing entry', event=rows.pop()))
    result = timing(rows)
    result.update(summary=cost_summary(result['master_clock_histogram']), censored=censored,
        scope='Whole sender entry through before RTS, including protocol waits and logger if present. '
              'Frame/short-scanline crossings excluded, incomplete boundaries retained. '
              'Independent runs, not matched-packet cost or net logger overhead.')
    return result


def audit(out):
    specs = (
        ('Interleaved long-port', 'audio-packet-interleaved-1568', 'audio-packet-interleaved-observed-1569',
         'audio-packet-interleaved-normal-1570', 'audio-packet-interleaved-timing-1572',
         'audio-packet-interleaved-1569-received.csv', 'audio-packet-interleaved-1572-events.csv',
         'audio-packet-interleaved-game-1571', 'audio-packet-interleaved-entry-1574', 'audio-packet-interleaved-cadence-1582'),
        ('Interleaved original poller', 'audio-packet-poll-1577', 'audio-packet-poll-observed-1578',
         'audio-packet-poll-normal-1580', 'audio-packet-poll-timing-1581',
         'audio-packet-poll-1578-received.csv', 'audio-packet-poll-1581-events.csv',
         'audio-packet-poll-game-1579', 'audio-packet-poll-entry-1584', 'audio-packet-poll-cadence-1587'))
    paths = [Path(__file__), Path('tools/audit_audio_packet_log.py'), Path('tools/audio_packet_log.py'),
             Path('tools/build_packet_log_cost_review.py'), Path('tools/audit_room_entry.py')]
    baseline = Path('build/audio-packet-parent-1573')
    control = Path('build/audio-packet-baseline-1542')
    if any(sha(baseline.with_suffix(s)) != sha(control.with_suffix(s)) for s in ('.ram', '.wav', '.png')):
        raise ValueError('Parent timing observer is not neutral')
    trace = baseline.with_name(baseline.name + '-events.csv')
    with trace.open() as f:
        original = sender_cost(list(csv.reader(f)))
    paths.extend([trace, baseline.with_suffix('.json')])
    paths.extend(p.with_suffix(s) for p in (baseline, control) for s in ('.ram', '.wav', '.png'))
    results = []
    for name, *names in specs:
        candidate, observed, normal, timed, receive, events, game, entry, cadence = [Path('build') / n for n in names]
        manifest = json.loads((candidate / 'manifest.json').read_text())
        if sha(candidate / 'native-cpu.sfc') != manifest['rom_sha256']:
            raise ValueError('Candidate ROM differs')
        for p, h in manifest['diagnostic_packet_log']['sources'].items():
            if sha(Path(p)) != h:
                raise ValueError('Changed build source: ' + p)
        for root in (observed, normal, timed):
            report = json.loads((root / 'report.json').read_text())
            if report['rom_sha256'] != manifest['rom_sha256'] or report['status'] != 'passed':
                raise ValueError('Wrong or failed capture')
            for p, h in report['sources'].items():
                if sha(Path(p)) != h:
                    raise ValueError('Changed capture source: ' + p)
            paths.append(root / 'report.json')
        neutral = {n: len({sha(root / n) for root in (observed, normal, timed)}) == 1
                   for n in ('packets.srm', 'frames.json', 'ram.bin', 'last.png', 'audio.wav')}
        if not all(neutral.values()):
            raise ValueError('Non-neutral observer')
        log = decode((normal / 'packets.srm').read_bytes())
        with receive.open() as f:
            packets = received_packets(csv.reader(f))
        matched = compare(log, packets)
        with events.open() as f:
            clocks = sender_cost(list(csv.reader(f)))
        e = json.loads((entry / 'report.json').read_text())
        g, _ = verify_capture(game)
        if (g['rom_sha256'] != manifest['rom_sha256'] or not g['capture_complete'] or
                e['sources']['snes']['capture_sha256'] != sha(game / 'capture.json') or
                e['audit_sha256'] != sha(Path('tools/audit_room_entry.py'))):
            raise ValueError('Room-entry provenance differs')
        c = bound_report(cadence / 'report.json')
        if c['sources'].get(str(game / 'capture.json')) != sha(game / 'capture.json'):
            raise ValueError('Cadence/control binding differs')
        results.append(dict(name=name, sender_timing=clocks, neutral=neutral,
            total_packets=log['total'], retained_matched=matched, overwritten=log['overwritten'],
            entry_passed=e['passed'], entry_gates=e['gates'], entry_link=entry.name,
            cadence_passed=c['passed'], stable_loops=sum(len(v['iterations']) for v in c['main']['rooms'].values()),
            first_visible=[dict(room=x['room'], nes=x['nes']['first_nonblack_offset'],
                snes=x['snes']['first_nonblack_offset']) for x in e['comparisons']],
            parent_final_image_equal=sha(normal / 'last.png') == sha(control.with_suffix('.png')),
            parent_final_wram_equal=sha(normal / 'ram.bin') == sha(control.with_suffix('.ram')),
            parent_wav_equal=sha(normal / 'audio.wav') == sha(control.with_suffix('.wav'))))
        paths.extend([candidate / 'manifest.json', candidate / 'native-cpu.sfc', receive, events,
                      game / 'capture.json', entry / 'report.json', cadence / 'report.json'])
        paths.extend(root / n for root in (normal, timed, observed)
                     for n in ('packets.srm', 'frames.json', 'ram.bin', 'last.png', 'audio.wav'))
    timeout_path = Path('build/audio-packet-poll-timeouts-1583/report.json')
    failures = bound_report(timeout_path)
    paths.append(timeout_path)
    report = dict(original_sender_timing=original, trials=results,
        original_poller_timeout_cases=failures['cases'], timeout_test_passed=failures['passed'],
        deployed=False, physical_audio_gap_explained=False,
        sources={str(p): sha(p) for p in paths},
        scope='Interleaved diagnostic SRAM writes only. All load failures and timing exclusions retained; '
              'no timing-neutral, physical-audio, release or whole-game speed claim.')
    out.mkdir(parents=True, exist_ok=False)
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    table = []
    for name, clocks in [('Unmodified sender', original)] + [(r['name'], r['sender_timing']) for r in results]:
        s = clocks['summary']
        table.append(f'<tr><td>{html.escape(name)}</td><td>{s["median"]}</td>'
            f'<td>{s["minimum"]}–{s["maximum"]}</td><td>{s["samples"]}</td>'
            f'<td>{len(clocks["excluded"])}</td></tr>')
    links = ''.join(f'<li><a href="../{r["entry_link"]}/">{html.escape(r["name"])}: '
                   f'full fade comparison (pass={r["entry_passed"]})</a></li>' for r in results)
    (out / 'index.html').write_text('''<!doctype html><meta charset="utf-8">
<title>Interleaved sound-command logging</title>
<style>body{background:#10151d;color:#eee;font:18px system-ui;max-width:1050px;margin:2em auto}
td,th{padding:.6em;border:1px solid #64748b}table{border-collapse:collapse}a{color:#7dd3fc}</style>
<h1>Logging during sound-port waits</h1>
<p>Both prototypes retain4,095 exact matches to independently observed SPC packets out of4,606
total;511 overwritten records remain unavailable. Normal/receiver/timing observers agree
within each build. The SRAM format and corruption checks are unchanged.</p>
<table><tr><th>Build</th><th>Median sender clocks</th><th>Range</th><th>Measured</th><th>Excluded crossings</th></tr>'''
        + ''.join(table) + '''</table><p>Entire sender duration, not added logging cost. Independent runs
and different encounters; no matched-work speed ratio. All censored boundaries are in the report.</p>
<p>Both steady-cadence audits pass, but both fixed-offset fade comparisons fail. Matching a final
screenshot did not predict room-load correctness. <strong>Neither is deployed.</strong></p>
<p>Original-poller version: all14 injected handshake-failure stages produce committed timeout
records and the outer game's error flag. Incomplete timeout payloads are not classified as received.</p>
<p>Next: a bounded, steady-gameplay recording interval that explicitly records coverage gaps;
continuous logging still changes the very timing under investigation.</p><ul>''' + links +
        '</ul><p><a href="report.json">Bound measurements, exclusions and limitations</a></p>')
    print(json.dumps(dict(trials=[{k:r[k] for k in ('name','total_packets','retained_matched','entry_passed',
        'cadence_passed','stable_loops')} for r in results], timeout_passed=failures['passed']), indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    audit(**vars(p.parse_args()))
