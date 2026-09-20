"""Separate packet-arrival cadence from post-receipt SPC service, without clock fitting."""
import argparse
from bisect import bisect_right
import csv
import html
import json
from pathlib import Path

import numpy as np

from tools.audit_dsp_latency import dac_tick, next_dac_sample, validate_trace
from tools.audit_main_display_latency import bound_report
from tools.audit_postpublish_keyon import load
from tools.benchmark_report import sha, verify_capture


def decompose(packets, ready):
    """Both endpoints are completed SPC write ticks, including the write's tick."""
    if not packets or set(ready) != set(range(1, len(packets)+1)):
        raise ValueError('Incomplete packet/ready coverage')
    services = []
    for number, packet in enumerate(packets, 1):
        received = packet['received_tick']
        end = ready[number]
        if packet['packet'] != number or received < 0 or end <= received:
            raise ValueError('Invalid service endpoints')
        if services and received <= services[-1]['ready_tick']:
            raise ValueError('Overlapping or reordered packet service')
        services.append(dict(packet=number, received_tick=received,
                             ready_tick=end, service_ticks=end-received))
    intervals = []
    for a, b in zip(services, services[1:]):
        received_gap = b['received_tick']-a['received_tick']
        ready_gap = b['ready_tick']-a['ready_tick']
        delta = b['service_ticks']-a['service_ticks']
        if ready_gap != received_gap+delta:
            raise ValueError('Clock decomposition failed')
        intervals.append(dict(first_packet=a['packet'], last_packet=b['packet'],
            received_gap_ticks=received_gap, ready_gap_ticks=ready_gap,
            service_delta_ticks=delta))
    return services, intervals


def summarize(values, rate):
    ticks = np.asarray(values, dtype=np.int64)
    if not len(ticks) or rate <= 0:
        raise ValueError('Empty timing population or invalid rate')
    keys = ('minimum', 'median', 'p99', 'maximum')
    quantiles = np.quantile(ticks, (0, .5, .99, 1))
    return dict(count=len(ticks), ticks=dict(zip(keys, map(float, quantiles))),
        milliseconds_at_nominal_rate=dict(zip(keys, map(float, quantiles*1000/(32*rate)))),
        standard_deviation_ticks=float(ticks.std()))


def stable_intervals(intervals, services, rows):
    starts = [r['audio_start_sample'] for r in rows]
    ends = [r['audio_start_sample']+r['audio']['samples'] for r in rows]
    kept, excluded = [], []
    for interval in intervals:
        a = services[interval['first_packet']-1]
        b = services[interval['last_packet']-1]
        first, last = (next_dac_sample(p['ready_tick']) for p in (a, b))
        lo, hi = bisect_right(starts, first)-1, bisect_right(starts, last)-1
        if not 0 <= lo <= hi < len(rows) or not first < ends[lo] or not last < ends[hi]:
            raise ValueError('Completion outside captured PCM')
        context = rows[lo:hi+1]
        stable = all(bytes.fromhex(r['game_ram_hex'])[0x100]&0xc0 == 0xc0 and
                     not r['native']['transition_state'] for r in context)
        record = dict(interval, first_frame=rows[lo]['frame'], last_frame=rows[hi]['frame'],
                      phase=rows[hi]['phase'])
        (kept if stable else excluded).append(record)
    if not kept:
        raise ValueError('No stable gameplay coverage')
    return kept, excluded


def review(candidate, capture, normal, edges, out):
    if out.exists():
        raise ValueError('Fresh output required')
    audit, writes, old_ready = load(capture, normal, candidate)
    receipt, rows = verify_capture(capture)
    prior = bound_report(edges/'report.json')
    if prior['sources'].get(str(capture/'capture.json')) != sha(capture/'capture.json'):
        raise ValueError('Audio edge report uses a different capture')
    for name, digest in prior['artifacts'].items():
        if sha(edges/name) != digest:
            raise ValueError('Changed edge artifact: '+name)
    trace = Path(receipt['dsp_latency_observer']['traces']['RCR_DSP_LATENCY_TRACE']['path'])
    with trace.open() as stream:
        packets, _, _ = validate_trace(list(csv.reader(stream)), rows, audit['pcm_samples'])
    # The legacy ready record is emitted BEFORE op_write's tick. Receipt was
    # already normalized by validate_trace. Normalize ready identically here.
    ready = {number: tick+1 for number, tick in old_ready.items()}
    services, intervals = decompose(packets, ready)
    kept, excluded = stable_intervals(intervals, services, rows)
    rate = audit['sample_rate']
    used = sorted({i[k] for i in kept for k in ('first_packet', 'last_packet')})
    stats = {key: summarize([i[key] for i in kept], rate) for key in
             ('received_gap_ticks', 'ready_gap_ticks', 'service_delta_ticks')}
    stats['service_ticks'] = summarize([services[n-1]['service_ticks'] for n in used], rate)
    # CPU coordinates are retained as coordinates, NOT subtracted from SPC
    # ticks or treated as retro_run indices. IPPU and callback epochs differ.
    buspath = Path(receipt['dsp_latency_observer']['traces']['RCR_AUDIO_BUS_TRACE']['path'])
    cpu = []; pending = []; current = []
    with buspath.open() as stream:
        for row in csv.reader(stream):
            event = dict(ippu_frame=int(row[1]), line=int(row[2]), cycle=int(row[3]),
                         native_id=int(row[4]), index=int(row[5]), value=int(row[6]), pc=row[7])
            if row[0] == 'W':
                pending.append(event)
            else:
                current.append(event)
                if len(current) == 23:
                    cpu.append(dict(first_port=current[0], last_port=current[-1],
                        original_shadow_writes=len(pending),
                        first_shadow=pending[0] if pending else None,
                        last_shadow=pending[-1] if pending else None))
                    pending, current = [], []
    if len(cpu) != len(services) or pending or current:
        raise ValueError('Incomplete CPU correspondence')
    received_ticks = [s['received_tick'] for s in services]
    write_ticks = [w['tick'] for w in writes]
    events = []
    for e in prior['events']:
        tick = dac_tick(e['sample'])
        at = bisect_right(received_ticks, tick)-1
        wi = bisect_right(write_ticks, tick)-1
        if at < 0 or wi < 0:
            raise ValueError('Audio edge precedes packet/write coverage')
        service = services[at]
        events.append(dict(sample=e['sample'], channel=e['channel'], frame=e['frame'], phase=e['phase'],
            contributions=e['contributions'], dac_tick=tick, service=service, cpu=cpu[at],
            ticks_since_receipt=tick-service['received_tick'],
            ticks_since_ready=tick-service['ready_tick'],
            latest_dsp_write=writes[wi], ticks_since_latest_dsp_write=tick-writes[wi]['tick']))
    controls = {}
    for label, altered in (('missing_ready', dict(list(ready.items())[1:])),
                           ('ready_before_receipt', {**ready, 1: packets[0]['received_tick']-1})):
        try:
            decompose(packets, altered)
        except ValueError:
            controls[label+'_rejected'] = True
        else:
            raise ValueError('Timing mutation survived: '+label)
    sources = {**prior['sources'], **audit['sources']}
    for p in (Path(__file__), Path('tools/audit_dsp_latency.py'), Path('tools/audit_postpublish_keyon.py'),
              Path('tools/audit_main_display_latency.py'), Path('tools/benchmark_report.py'),
              Path('tests/test_audio_pipeline_timing.py'), edges/'report.json',
              capture/'timeline.json', normal/'timeline.json', capture/'audio.wav', normal/'audio.wav'):
        sources[str(p)] = sha(p)
    longest = sorted(kept, key=lambda x: x['ready_gap_ticks'], reverse=True)[:12]
    report = dict(passed=True, rom_sha256=receipt['rom_sha256'], packet_count=len(services),
        nominal_sample_rate=rate, stable_intervals=len(kept), excluded_intervals=len(excluded),
        statistics=stats, longest=longest, selected_audio_edges=events,
        services=services, intervals=kept, exclusions=excluded, controls=controls, sources=sources,
        pop_free_verified=False, physical_verified=False, release_ready=False,
        scope='Exact consecutive completed receipt/ready SPC writes. Stable gameplay filter uses '
        'completion callback contexts, task C0 and no transition flag; pause and busy are retained. '
        'No CPU/SPC clock fit. Arrival means the LAST packet byte, not sound-driver entry. '
        'Service includes voice setup before ready, not complete audible DSP response. '
        'Observed interval decomposition is not an audibility or NES-equivalence verdict.')
    cards = []
    for key, stat in stats.items():
        cards.append('<tr><td>'+html.escape(key)+'</td>'+''.join(
            f'<td>{v:.4f}</td>' for v in stat['milliseconds_at_nominal_rate'].values())+'</tr>')
    detail = []
    for i in longest:
        detail.append(f'<tr><td>{i["last_packet"]}</td><td>{i["first_frame"]}–{i["last_frame"]}</td>'
            f'<td>{html.escape(i["phase"])}</td>'+''.join(
                f'<td>{i[k]*1000/(32*rate):.4f}</td>' for k in
                ('received_gap_ticks','service_delta_ticks','ready_gap_ticks'))+'</tr>')
    out.mkdir(parents=True)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Audio pipeline timing</title>'
        '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:2em auto}'
        'a{color:cyan}td,th{text-align:right;padding:.6em;border-bottom:1px solid #567}td:first-child{text-align:left}'
        'table{border-collapse:collapse}code{color:#aef}</style><h1>Where the audio timing varies</h1>'
        '<p>Unchanged offline cartridge3032. Neither MiSTer accessed. Actual SPC clocks; no waveform fit.</p>'
        '<p><code>Ready interval = receipt interval + change in post-receipt service time</code></p>'
        f'<p>{len(services):,} packets authenticated; {len(kept):,} stable gameplay intervals. '
        'Receipt is the last packet byte. These traces cannot yet separate original driver timing from CPU transfer.</p>'
        '<h2>Measured timings (milliseconds at native nominal sample rate)</h2>'
        '<table><tr><th>Population</th><th>Minimum</th><th>Median</th><th>p99</th><th>Maximum</th></tr>'+
        ''.join(cards)+'</table><h2>Longest completion intervals</h2>'
        '<table><tr><th>Packet</th><th>Callback frames</th><th>Phase</th><th>Arrival gap ms</th>'
        '<th>Service change ms</th><th>Ready gap ms</th></tr>'+''.join(detail)+'</table>'
        '<p>Variable completion timing must not automatically be called a pop or dropped packet. '
        'Silence, task transitions and excluded intervals remain in the JSON. Pause and busy states are not removed. '
        'Ready is a software acknowledgment, not the final audible response of a voice.</p>'
        '<p>The same twelve previously selected waveform edges retain exact SPC and raw CPU context; '
        'no replacement events selected to favor an explanation.</p>'
        '<p><a href="../final-batch-audio-edges-3058/">Frozen audio clips and collages</a> · '
        '<a href="report.json">Full hash-bound timing evidence and negative controls</a></p>')
    for name, digest in sources.items():
        if sha(Path(name)) != digest:
            raise ValueError('Changed source: '+name)
    report['artifacts'] = {'index.html': sha(out/'index.html')}
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(packets=len(services), intervals=len(kept), statistics=stats, controls=controls)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'capture', 'normal', 'edges', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    review(**vars(parser.parse_args()))
