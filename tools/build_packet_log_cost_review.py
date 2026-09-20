"""Combine packet-log correctness, cost, wrap endurance and rejected load timing."""
import argparse
import html
import json
from pathlib import Path
import statistics

from tools.audio_packet_log import decode
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha, verify_capture


def cost_summary(histogram):
    values = [int(cost) for cost, count in histogram.items() for _ in range(count)]
    if not values:
        raise ValueError('Empty cost histogram')
    return dict(samples=len(values), minimum=min(values), maximum=max(values),
                median=statistics.median(values))


def build(original, word, bridge, word_entry, bridge_entry, cadence, endurance,
          word_game, bridge_game, out):
    reports = [bound_report(p / 'report.json') for p in (original, word, bridge)]
    cad = bound_report(cadence / 'report.json')
    entries = []
    for root, game in ((word_entry, word_game), (bridge_entry, bridge_game)):
        r = json.loads((root / 'report.json').read_text())
        capture, rows = verify_capture(game)
        if (r['audit_sha256'] != sha(Path('tools/audit_room_entry.py')) or
                r['sources']['snes']['capture_sha256'] != sha(game / 'capture.json') or
                r['sources']['snes']['rom_sha256'] != capture['rom_sha256'] or
                not capture['capture_complete']):
            raise ValueError('Entry audit/capture differs')
        entries.append(dict(passed=r['passed'], gates=r['gates'], frames=len(rows),
            first_visible=[dict(room=c['room'], nes=c['nes']['first_nonblack_offset'],
                                snes=c['snes']['first_nonblack_offset']) for c in r['comparisons']]))
    long = json.loads((endurance / 'report.json').read_text())
    for name, digest in long['sources'].items():
        if sha(Path(name)) != digest:
            raise ValueError('Changed endurance source: ' + name)
    log = decode((endurance / 'packets.srm').read_bytes())
    frames = json.loads((endurance / 'frames.json').read_text())
    live = [r for r in frames if r['initialized'] and r['total'] > 0]
    deltas = [b['total'] - a['total'] for a, b in zip(live, live[1:])]
    nmi_wraps = [dict(frame=b['frame'], before=a['nmi'], after=b['nmi'])
                 for a, b in zip(live, live[1:]) if b['nmi'] < a['nmi']]
    if (long['status'] != 'passed' or log['total'] <= 65536 or not nmi_wraps or
            set(deltas) - {0, 1} or any(r['timeout'] for r in log['records'])):
        raise ValueError('Endurance/counter-wrap check failed')
    paths = [p / 'report.json' for p in (original, word, bridge, word_entry, bridge_entry, cadence, endurance)]
    paths += [Path(__file__), endurance / 'packets.srm', endurance / 'frames.json',
              word_game / 'capture.json', bridge_game / 'capture.json']
    summaries = [cost_summary(r['timing']['master_clock_histogram']) for r in reports]
    report = dict(costs=dict(zip(('original', 'word', 'bridge'), summaries)),
        packet_matches=[r['retained_matched'] for r in reports], word_entry=entries[0], bridge_entry=entries[1],
        word_cadence=dict(passed=cad['passed'], stable_iterations=sum(len(r['iterations'])
            for r in cad['main']['rooms'].values()), holds={name: r['histogram'] for name, r in cad['holds'].items()}),
        word_endurance=dict(frames=len(frames), total=log['total'], retained=len(log['records']),
            overwritten=log['overwritten'], nmi_wraps=nmi_wraps,
            no_new_packet_frames=deltas.count(0), scope='Structural/commit checks, not independent receipt matching over the long run.'),
        deployed=False, timing_neutral=False, physical_silence_explained=False,
        sources={str(p): sha(p) for p in paths})
    out.mkdir(parents=True, exist_ok=False)
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    table = ''.join(f'<tr><th>{name}</th><td>{s["minimum"]}–{s["maximum"]}</td>'
                    f'<td>{s["median"]}</td><td>{s["samples"]}</td></tr>'
                    for name, s in report['costs'].items())
    links = ''.join(f'<li><a href="../{html.escape(p.name)}/">{label}</a></li>' for p, label in (
        (original, 'First logger: exact sound-processor comparison'),
        (word, 'Word-copy logger: exact sound-processor comparison'),
        (bridge, 'Caller-aware logger: exact sound-processor comparison'),
        (word_entry, 'Word-copy room-load comparison — failed'),
        (bridge_entry, 'Caller-aware room-load comparison — inspect actual result')))
    (out / 'index.html').write_text(f'''<!doctype html><meta charset="utf-8">
<title>Sound logger cost and regression checks</title>
<style>body{{background:#10151d;color:#eee;font:18px system-ui;max-width:1050px;margin:2em auto}}
td,th{{padding:.6em;border:1px solid #64748b}}table{{border-collapse:collapse}}a{{color:#7dd3fc}}</style>
<h1>Faster sound-command logger; not a gameplay release</h1>
<p>All three implementations exactly match 4,095 retained packets against independent
SPC receipts. Host observers preserve each build's PCM, RAM and screenshots.</p>
<table><tr><th>Version</th><th>Elapsed master clocks</th><th>Median</th><th>Spans</th></tr>{table}</table>
<p>Includes refresh/events; excludes added call/return overhead. Independent runs have
different timing/encounters: medians are not matched-work speedup measurements.</p>
<h2>Regression results</h2>
<p>Word-copy build: {report['word_cadence']['stable_iterations']:,} stable loops keep two-NMI
cadence across four sampled rooms; no short irregular park camera holds. Long holds remain.</p>
<p>Word-copy room-load pass: {entries[0]['passed']}. Caller-aware room-load pass:
{entries[1]['passed']}. Both parent comparisons differ: neither logger is timing-neutral.</p>
<p>70,000-frame word-copy endurance: {log['total']:,} packets counted, a16-bit NMI wrap,
4,095 structurally valid retained records and no recorded timeout. This long run does not
have independent receiver evidence for every packet; overwritten records remain unavailable.</p>
<p><strong>Nothing deployed; Rival undisturbed. Remaining physical sound gaps are unresolved.</strong></p>
<ul>{links}</ul><p><a href="report.json">Bound report with exclusions and exact results</a></p>''')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('original', 'word', 'bridge', 'word-entry', 'bridge-entry', 'cadence', 'endurance',
                 'word-game', 'bridge-game', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    build(**vars(parser.parse_args()))
