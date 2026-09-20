"""Current CPU generation/transfer and SPC receipt/ready timing, without clock-origin fitting."""
import argparse
import csv
import html
import json
from pathlib import Path
import time
from tools.audit_audio_pipeline import stages, intervals, distribution
from tools.analyze_spc_ack import analyze as acknowledgements
from tools.review_command_priority import bound
from tools.benchmark_report import sha, verify_capture

CPU_MS = 11000/236250000
SPC_MS = 1000/(32040*32)


def spc_pairs(rows):
    result=[];active=None
    for r in rows:
        if r[0] not in ('P','R') or not int(r[1]):continue
        if len(r)!=5:raise ValueError('Malformed receipt/ready event')
        event=dict(packet=int(r[1]),tick=int(r[2]))
        if r[0]=='P':
            if active is not None or event['packet']!=len(result)+1:raise ValueError('Missing/reordered receipt')
            if result and event['tick']<=result[-1]['ready']:raise ValueError('Overlapping SPC pairs')
            active=event
        else:
            if active is None or active['packet']!=event['packet'] or event['tick']<=active['tick']:
                raise ValueError('Missing, duplicate or premature ready')
            result.append(dict(packet=event['packet'],received=active['tick'],ready=event['tick'],
                               processing=event['tick']-active['tick']))
            active=None
    if active is not None or not result:raise ValueError('Censored/empty SPC pairs')
    return result


def decompose_spc(a,b):
    received=b['received']-a['received'];processing=b['processing']-a['processing']
    ready=b['ready']-a['ready']
    if received+processing!=ready:raise ValueError('Invalid SPC decomposition')
    return dict(receive_gap_ticks=received,processing_change_ticks=processing,ready_gap_ticks=ready)


def audit(capture,timing,candidate,out):
    if out.exists():raise ValueError('Fresh report required')
    started=time.monotonic()
    bound(capture/'current-pipeline.json');proof=bound(capture/'pipeline-capture.json')
    if not proof['observer_neutral']:raise ValueError('Non-neutral pipeline')
    receipt,timeline=verify_capture(capture)
    prior=bound(timing/'report.json')
    if prior['summary']['rom_sha256']!=receipt['rom_sha256']:raise ValueError('Different cartridge')
    spans=Path(receipt['span_trace']['path']);ack=Path(receipt['spc_ack_trace']['path'])
    raw=list(csv.reader(spans.open()));packets=stages(raw)
    dsp=Path(receipt['dsp_latency_observer']['traces']['RCR_DSP_LATENCY_TRACE']['path'])
    dsp_rows=list(csv.reader(dsp.open()));spc=spc_pairs(dsp_rows)
    meta=json.loads((candidate/'manifest.json').read_text())
    acked=acknowledgements(list(csv.reader(ack.open())),paired=True,
        engine_size=meta['sweep_driver_layout']['engine_bytes'])
    if len(packets)!=len(spc) or len(packets)!=acked['acknowledged_packets']:raise ValueError('Packet coverage mismatch')
    ack_delays=[]
    for p,a in zip(packets,acked['completions']):
        delta=p['done']['clock']-a['absolute_clock']
        if p['done']['native_id']!=a['nmi'] or not 0<delta<500:raise ValueError('CPU completion/ACK mismatch')
        ack_delays.append(delta)
    selected={r['packet'] for r in prior['stable']}
    measured,excluded=intervals(packets,selected)
    # Historical origin labels classify common5F00 as "early", even when
    # entered by the newer regular IRQ. Do not inherit those path claims.
    for item in measured:
        item.pop('origin_pair')
        k=item['last_packet'];s=decompose_spc(spc[k-2],spc[k-1]);item['spc']=s
        item['cpu_ms']=dict(entry_gap=item['entry_gap']*CPU_MS,
            completion_gap=item['completion_gap']*CPU_MS,
            stage_changes={key:value*CPU_MS for key,value in item['stage_changes'].items()})
        item['spc_ms']={key.replace('_ticks','_ms'):value*SPC_MS for key,value in s.items()}
    by_packet={r['packet']:r for r in prior['stable']+prior['excluded']}
    for k in range(2,len(spc)+1):
        gap=(spc[k-1]['ready']-spc[k-2]['ready'])*SPC_MS
        if abs(gap-by_packet[k]['gap_ms'])>1e-10:raise ValueError('Changed frozen SPC interval')
    negatives=[]
    driver_missing=next(j for j,v in enumerate(raw) if v[0]=='1')
    ready_missing=next(j for j,v in enumerate(dsp_rows) if v[0]=='R' and int(v[1])>0)
    for name,rows,parser in [('missing driver return',raw[:driver_missing]+raw[driver_missing+1:],stages),
            ('missing SPC ready',dsp_rows[:ready_missing]+dsp_rows[ready_missing+1:],spc_pairs)]:
        try:parser(rows)
        except ValueError:negatives.append(name)
        else:raise ValueError('Missing-event control escaped')
    worst=sorted(measured,key=lambda r:r['spc']['ready_gap_ticks'],reverse=True)[:12]
    summary=dict(rom_sha256=receipt['rom_sha256'],frames=len(timeline),packets=len(packets),
        wrapped_driver_calls=sum(bool(p['driver']) for p in packets),
        packets_without_wrapped_driver=[p['packet'] for p in packets if not p['driver']],
        measured_intervals=len(measured),excluded_intervals=len(excluded),
        processing_ms=distribution([p['processing']*SPC_MS for p in spc]),
        costs_ms={key:distribution([r['current_costs'][key]*CPU_MS for r in measured]) for key in ('driver','post_driver','bridge_setup','transfer')},
        ack_to_sender_done_clocks=distribution(ack_delays),negative_controls_rejected=negatives,
        capture_seconds=bound(capture/'current-pipeline.json')['elapsed_seconds'],release_ready=False)
    paths=[Path(__file__),Path('tests/test_current_audio_pipeline.py'),Path('tools/audit_audio_pipeline.py'),
           Path('tools/analyze_spc_ack.py'),Path('tools/review_command_priority.py'),
           capture/'current-pipeline.json',capture/'pipeline-capture.json',capture/'capture.json',
           timing/'report.json',spans,ack,dsp,candidate/'manifest.json']
    sources={str(p):sha(p) for p in paths}
    out.mkdir()
    table=''
    for r in worst:
        c=r['cpu_ms'];s=r['spc_ms']
        table+='<tr>'+''.join(f'<td>{v}</td>' for v in [r['last_packet'],r['frame'],
            *(f'{v:.3f}' for v in (c['entry_gap'],c['stage_changes']['driver'],c['stage_changes']['transfer'],
                                    s['receive_gap_ms'],s['processing_change_ms'],s['ready_gap_ms']))])+'</tr>'
    body='''<!doctype html><meta charset="utf-8"><title>3955 sound generation and delivery</title>
<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1250px;margin:30px auto}a{color:cyan}pre{white-space:pre-wrap}td,th{padding:7px;text-align:right;border-bottom:1px solid #456}table{border-collapse:collapse}</style>
<h1>3955: sound-generation timing and delivery timing separated</h1>
<p>Unchanged ROM. Fresh sparse observation preserves all9,090 frames and native PCM. Every CPU completion is joined to its actual acknowledgement; all8,641 SPC receipt/ready pairs are retained. CPU and SPC decompositions are exact within their own clocks, with no fitted clock origin or waveform alignment.</p>
<p>The earlier path label “early” is not reused: the common sound wrapper also serves the normal IRQ. Entry scanline and retained/depth flags remain in JSON. No missing-driver interval or transition is silently discarded.</p>
<h2>Longest stable SPC-ready gaps, milliseconds</h2>
<table><tr><th>Packet</th><th>CPU frame</th><th>CPU entry gap</th><th>Δ driver</th><th>Δ transfer</th><th>SPC receipt gap</th><th>Δ SPC processing</th><th>SPC ready gap</th></tr>'''+table+'''</table>
<p>CPU entry gap plus all four signed CPU stage changes equals CPU completion gap. SPC receipt gap plus signed processing change equals SPC-ready gap. The table omits small post-driver/bridge columns for readability; all terms and every measured/excluded interval are retained in JSON. Ready is a protocol event, not proof of acoustic onset or pop-free sound.</p>
<p><a href="../early-oam-live-half-audio-review-3962/">Untouched native baseline audio</a> · <a href="report.json">All intervals, raw stage records and bindings</a> · <a href="https://github.com/struktured-labs/river-city-ransom-snes/issues/6">Audio issue6</a></p>
<details><summary>Coverage and costs</summary><pre>'''+html.escape(json.dumps(summary,indent=2))+'</pre></details>'
    (out/'index.html').write_text(body)
    report=dict(summary=summary,packets=packets,spc_pairs=spc,intervals=measured,excluded=excluded,
        original_audio_excluded=prior['excluded'],worst=worst,sources=sources,
        seconds=time.monotonic()-started,artifacts={'index.html':sha(out/'index.html')},scope=__doc__)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(packets=len(packets),measured=len(measured),excluded=len(excluded),
                         processing_ms=summary['processing_ms'],seconds=report['seconds'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('capture','timing','candidate','out'):p.add_argument('--'+k,type=Path,required=True)
    audit(**vars(p.parse_args()))
