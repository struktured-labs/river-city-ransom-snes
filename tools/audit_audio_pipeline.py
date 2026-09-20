"""Attribute measured CPU publication intervals to original driver scheduling and actual stage costs."""
import argparse
from collections import Counter, defaultdict
import csv
import html
import json
from pathlib import Path

import numpy as np

from tools.analyze_spc_ack import analyze as ack_analyze
from tools.audit_main_display_latency import bound_report
from tools.audit_postpublish_keyon import load
from tools.benchmark_report import sha


def stages(raw):
    packets = []; driver = None; active = None; origin = None; previous = -1
    for row in raw:
        if len(row) != 16:
            raise ValueError('Malformed CPU stage trace')
        keys = ('kind','frame','line','cycle','clock','pc','native_id','task','transition',
                'busy','pause','state3f','depth','retained','state1c87','ppu_ctrl')
        e = dict(zip(keys, (int(v, 16 if i == 5 else 10) for i, v in enumerate(row))))
        if e['clock'] <= previous:
            raise ValueError('Nonmonotonic CPU clock')
        previous = e['clock']; kind = e['kind']
        if kind in (0, 1, 7, 8, 10, 12) and not 0xc1 <= e['pc'] >> 16 <= 0xc8:
            raise ValueError('Replicated point outside original game banks')
        if kind in (7, 8):
            origin = e
        if kind == 0:
            if driver is not None or active is not None:
                raise ValueError('Nested or unconsumed driver')
            driver = dict(entry=e, origin=origin if origin and origin['native_id'] == e['native_id'] else None)
        elif kind == 1:
            if driver is None or 'exit' in driver or driver['entry']['native_id'] != e['native_id']:
                raise ValueError('Unmatched sound-driver return')
            driver['exit'] = e
        elif kind == 2:
            if active is not None or (driver and 'exit' not in driver):
                raise ValueError('Publication overlapped another stage')
            active = dict(packet=len(packets)+1, bridge=e, driver=driver, byte_entries=[],
                driver_same_event=bool(driver and driver['entry']['native_id'] == e['native_id']))
            driver = None
        elif kind in (3, 4, 5, 6):
            if active is None or e['native_id'] != active['bridge']['native_id']:
                raise ValueError('Unowned sender stage')
            if kind == 4:
                if 'sender' not in active or 'done' in active:
                    raise ValueError('Byte outside transfer')
                active['byte_entries'].append(e)
            else:
                key = {3:'sender', 5:'done', 6:'return'}[kind]
                if key in active:
                    raise ValueError('Duplicate sender stage')
                active[key] = e
                if kind == 5 and len(active['byte_entries']) != 12:
                    raise ValueError('Missing paired byte iterations')
                if kind == 6:
                    if 'sender' not in active or 'done' not in active:
                        raise ValueError('Missing sender completion')
                    packets.append(active); active = None
    if not packets or active or driver:
        raise ValueError('Incomplete stage coverage')
    return packets


def classify(p):
    d = p['driver']
    if not d:
        return 'no_driver'
    if not d['origin']:
        return 'other'
    return {7:'early', 8:'normal_exit'}[d['origin']['kind']]


def intervals(packets, selected):
    kept = []; excluded = []
    for a, b in zip(packets, packets[1:]):
        if b['packet'] not in selected or any(not p['driver_same_event'] for p in (a,b)):
            excluded.append(dict(last_packet=b['packet'], reason='outside frozen gameplay interval or missing/split-event driver'))
            continue
        def costs(p):
            return dict(driver=p['driver']['exit']['clock']-p['driver']['entry']['clock'],
                post_driver=p['bridge']['clock']-p['driver']['exit']['clock'],
                bridge_setup=p['sender']['clock']-p['bridge']['clock'],
                transfer=p['done']['clock']-p['sender']['clock'])
        ca, cb = costs(a), costs(b)
        deltas = {key: cb[key]-ca[key] for key in ca}
        entry_gap = b['driver']['entry']['clock']-a['driver']['entry']['clock']
        done_gap = b['done']['clock']-a['done']['clock']
        if entry_gap+sum(deltas.values()) != done_gap:
            raise ValueError('CPU stage decomposition failed')
        kept.append(dict(last_packet=b['packet'], frame=b['bridge']['frame'],
            origin_pair=classify(a)+' → '+classify(b), entry_gap=entry_gap, completion_gap=done_gap,
            stage_changes=deltas, previous_costs=ca, current_costs=cb,
            previous_entry=a['driver']['entry'], current_entry=b['driver']['entry']))
    if not kept:
        raise ValueError('No covered CPU intervals')
    return kept, excluded


def distribution(values):
    if not values:
        raise ValueError('Empty timing population')
    return dict(count=len(values), **dict(zip(('minimum','median','p99','maximum'),
                                            map(float, np.quantile(values, (0,.5,.99,1))))))


def audit(candidate, capture, control, timing, out):
    if out.exists():
        raise ValueError('Fresh output required')
    binding = bound_report(capture/'pipeline-capture.json')
    prior = bound_report(timing/'report.json')
    proof, _, ready = load(capture, control, candidate)
    if prior['rom_sha256'] != sha(candidate/'native-cpu.sfc'):
        raise ValueError('Different timing cartridge')
    if prior['sources'].get(str(control/'capture.json')) != sha(control/'capture.json'):
        raise ValueError('Different frozen timing control')
    # Sources of the receipt and observer already verify the full timeline and
    # every trace; enumerate packets again using independent CPU-stage clocks.
    receipt = json.loads((capture/'capture.json').read_text())
    span = Path(receipt['span_trace']['path']); ack = Path(receipt['spc_ack_trace']['path'])
    with span.open() as f:
        packets = stages(csv.reader(f))
    manifest = json.loads((candidate/'manifest.json').read_text())
    with ack.open() as f:
        acknowledgments = ack_analyze(list(csv.reader(f)), paired=True,
                                     engine_size=manifest['sweep_driver_layout']['engine_bytes'])
    if len(packets) != len(ready) or len(packets) != acknowledgments['acknowledged_packets']:
        raise ValueError('CPU/ACK/SPC packet counts differ')
    for p, a in zip(packets, acknowledgments['completions']):
        if p['done']['native_id'] != a['nmi'] or not 0 < p['done']['clock']-a['absolute_clock'] < 500:
            raise ValueError('Sender completion is not its actual ACK')
    selected = {i['last_packet'] for i in prior['intervals']}
    measured, excluded = intervals(packets, selected)
    groups = defaultdict(list)
    for interval in measured:
        groups[interval['origin_pair']].append(interval)
    summary = {key: dict(entry_gap=distribution([v['entry_gap'] for v in values]),
        completion_gap=distribution([v['completion_gap'] for v in values])) for key, values in groups.items()}
    longest = sorted(measured, key=lambda v:v['completion_gap'], reverse=True)[:12]
    # Remove one actual return marker, not a fabricated ROM mutation.
    with span.open() as f:
        damaged = list(csv.reader(f))
    damaged.pop(next(i for i, row in enumerate(damaged) if row[0] == '1'))
    try:
        stages(damaged)
    except ValueError:
        negative = True
    else:
        raise ValueError('Missing driver return survived')
    sources = {**binding['sources'], **prior['sources'], **proof['sources']}
    for path in (Path(__file__), Path('tools/analyze_spc_ack.py'),
                 Path('tests/test_audio_pipeline_stages.py'), capture/'pipeline-capture.json', timing/'report.json'):
        sources[str(path)] = sha(path)
    report = dict(passed=True, sources=sources, packets=len(packets), driver_calls=sum(bool(p['driver']) for p in packets),
        origins=dict(Counter(classify(p) for p in packets)), covered_intervals=len(measured),
        split_event_drivers=[p for p in packets if p['driver'] and not p['driver_same_event']],
        excluded_intervals=excluded, groups=summary, longest=longest, intervals=measured,
        missing_return_mutation_rejected=negative, observer_neutral=True,
        pop_free_verified=False, physical_verified=False, release_ready=False,
        scope='Existing sparse CPU observer with elapsed master clocks including DMA/interrupts. '
        'Full9,248-frame input/game/video/PCM equality with prior DSP recording. All packet ACKs joined '
        'by verified order and exact native event identity. Frozen SPC gameplay intervals only; '
        'missing-driver intervals excluded explicitly, no interpolation. No CPU/SPC epoch fit, '
        'NES equivalence or audibility verdict. Driver origins use actual early/normal-return entries.')
    out.mkdir(parents=True)
    rows = ''.join('<tr><td>'+html.escape(key)+'</td>'+''.join(f'<td>{v:.0f}</td>' for v in
        (s['entry_gap']['count'],s['entry_gap']['minimum'],s['entry_gap']['median'],s['entry_gap']['maximum']))+'</tr>'
        for key,s in summary.items())
    detail = ''.join('<tr><td>'+str(i['last_packet'])+'</td><td>'+html.escape(i['origin_pair'])+'</td>'+''.join(
        f'<td>{v}</td>' for v in (i['entry_gap'],*i['stage_changes'].values(),i['completion_gap']))+'</tr>' for i in longest)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>CPU audio stage timing</title>'
        '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1200px;margin:2em auto}'
        'a{color:cyan}td,th{padding:.5em;text-align:right;border-bottom:1px solid #567}table{border-collapse:collapse}'
        'td:first-child{text-align:left}</style><h1>Audio timing: alternating driver schedules</h1>'
        '<p>Unchanged candidate3032; neither MiSTer accessed. The sparse trace reproduces every game frame '
        'and PCM sample. Units below are elapsed CPU master clocks, not SPC clocks or exclusive instruction costs.</p>'
        '<h2>Driver-entry intervals by actual path</h2><table><tr><th>Previous → current</th><th>Count</th>'
        '<th>Minimum</th><th>Median</th><th>Maximum</th></tr>'+rows+'</table>'
        '<h2>Longest covered sender-completion intervals</h2><p>Entry gap plus all four signed stage changes '
        'equals completion gap exactly.</p><table><tr><th>Packet</th><th>Paths</th><th>Entry gap</th>'
        '<th>Δ driver</th><th>Δ post-driver</th><th>Δ bridge</th><th>Δ transfer</th><th>Completion gap</th></tr>'+detail+
        '</table><p>This supports investigating the alternating early-deferred/normal-exit schedule. '
        'It does not by itself identify audible pops or justify dropping game sound updates.</p>'
        '<p><a href="report.json">Bound stage timings and exclusions</a> · '
        '<a href="../final-batch-audio-timing-3061/">SPC timing</a> · '
        '<a href="../final-batch-audio-edges-3058/">Frozen listening clips</a></p>')
    for path, digest in sources.items():
        if sha(Path(path)) != digest:
            raise ValueError('Changed source: '+path)
    report['artifacts'] = {'index.html': sha(out/'index.html')}
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('packets','driver_calls','origins','covered_intervals','groups')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','capture','control','timing','out'):
        parser.add_argument('--'+name,type=Path,required=True)
    audit(**vars(parser.parse_args()))
