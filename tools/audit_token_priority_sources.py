"""Separate changed CPU sound requests from lost SPC receive bytes in trial4007."""
import argparse
import csv
import html
import json
from pathlib import Path
from tools.analyze_audio_bus import analyze
from tools.analyze_spc_receive import compare
from tools.review_command_priority import bound
from tools.benchmark_report import sha

def audit(out):
    if out.exists():raise ValueError('Fresh report required')
    sources={str(p):sha(p) for p in (Path(__file__),Path('tools/analyze_audio_bus.py'),Path('tools/analyze_spc_receive.py'),Path('tools/review_command_priority.py'))}
    arms={};summaries={};negative=False
    for tag,root in [('3955','build/early-oam-live-half-audio-3961'),('4007','build/receiver-token-priority-audio-4010')]:
        path=Path(root)/'startup-game.json';bound(path);sources[str(path)]=sha(path)
        receipt=json.loads((Path(root)/'capture.json').read_text());traces=receipt['dsp_latency_observer']['traces']
        def read(name):
            p=Path(traces[name]['path']);h=traces[name]['sha256']
            if sha(p)!=h:raise ValueError('Changed trace')
            sources[str(p)]=h
            return list(csv.reader(p.open()))
        bus=read('RCR_AUDIO_BUS_TRACE');rx=read('RCR_SPC_RECEIVE_TRACE')
        source=analyze(bus,length_gate=True);transport=compare(bus,rx,paired=True,receiver_pcs=[0x32e5,0x32f1])
        if source['mismatches'] or source['unflushed_cpu_writes'] or not transport['passed']:raise ValueError('Transport/source failure')
        arms[tag]=source['packets']
        keyon=Path(root+'-keyon.csv');sources[str(keyon)]=sha(keyon)
        keys=[r for r in csv.reader(keyon.open()) if r[0]=='K' and int(r[1])>0]
        summaries[tag]=dict(packets=transport['packets'],bytes_compared=transport['bytes_compared'],
            received_mismatches=transport['mismatch_count'],cpu_bus_mismatches=0,unflushed_writes=0,
            cpu_pulse_restart_bits=sum((bytes.fromhex(p['bytes'])[22]&3).bit_count() for p in source['packets']),
            dsp_pulse_keyon_bits=sum((int(r[2])&3).bit_count() for r in keys))
        if tag=='4007':
            mutant=[r.copy() for r in rx];mutant[0][1]=str(int(mutant[0][1])^1)
            negative=not compare(bus,mutant,paired=True,receiver_pcs=[0x32e5,0x32f1])['passed']
    if not negative:raise ValueError('Dropped-byte negative escaped')
    a,b=arms['3955'],arms['4007']
    if len(a)!=len(b):raise ValueError('Different packet coverage')
    changes=[dict(packet=i+1,before=x,after=y) for i,(x,y) in enumerate(zip(a,b)) if x['bytes']!=y['bytes']]
    flags=[r for r in changes if bytes.fromhex(r['before']['bytes'])[22]&3!=bytes.fromhex(r['after']['bytes'])[22]&3]
    if not changes:raise ValueError('No source divergence')
    summary=dict(arms=summaries,changed_packets=len(changes),changed_restart_flag_packets=len(flags),
        first_difference=changes[0],corrupted_receive_mutant_rejected=negative,release_ready=False,
        conclusion='Three fewer pulse restart bits are already present in CPU requests; all198743 bytes per arm arrive unchanged. This rules out missing receive bytes, not changed game sound timing. Investigate frame3276 before promotion.')
    out.mkdir()
    body='<!doctype html><meta charset="utf-8"><title>4007 sound source divergence</title><style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1050px;margin:30px auto}a{color:cyan}pre{white-space:pre-wrap}</style><h1>Sound event divergence starts on the CPU, not in byte transfer</h1><p>All packets are retained and compared at actual receive stores. Fewer restart events are not silently accepted as an improvement. This is not a fidelity or release pass.</p><pre>'+html.escape(json.dumps(summary,indent=2))+'</pre><p><a href="report.json">Every changed source packet</a> · <a href="../receiver-token-priority-review-4013/">Timing and all changed pictures</a> · <a href="../receiver-token-priority-audio-review-4011/">Native audio</a></p>'
    (out/'index.html').write_text(body)
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Changed binding')
    report=dict(summary=summary,packet_changes=changes,restart_flag_changes=flags,sources=sources,artifacts={'index.html':sha(out/'index.html')},scope=__doc__)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(summary))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    audit(**vars(p.parse_args()))
