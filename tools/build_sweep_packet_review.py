"""Source/artifact-bound review of executed sweep event transport components."""
import argparse
import json
from pathlib import Path

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha


def build(producer,receiver,out):
    cpu=bound_report(producer);spc=bound_report(receiver)
    if not cpu['passed'] or not spc['passed']:raise ValueError('Failed component proof')
    sources={**cpu['sources'],**spc['sources'],str(producer):sha(producer),str(receiver):sha(receiver),
             str(Path(__file__)):sha(Path(__file__))}
    roots=[producer.parent/f'direct-{i}' for i in range(len(cpu['direct']))]
    roots += [producer.parent/f'fused-{channel}-{first}' for channel in range(8) for first in range(0,32,8)]
    for root,record in zip(roots,cpu['direct']+cpu['fused']):
        for name,key in (('test.sfc','rom_sha256'),('receipt.json','receipt_sha256'),('memory.ram','ram_sha256')):
            path=root/name
            if sha(path)!=record[key]:raise ValueError('Changed CPU execution artifact: '+str(path))
            sources[str(path)]=record[key]
    out.mkdir(parents=True,exist_ok=False)
    result=dict(dataset_verified=True,release_ready=False,physical_audio_verified=False,
        cpu_cases=cpu['direct_cases']+cpu['fused_cases'],spc_cases=spc['cases'],
        delayed_cases=spc['delayed_cases'],verified_cpu_runs=len(roots),sources=sources,
        scope='Executed CPU metadata generation and real SPC receiver/adapter/KON components. '
        'Not simultaneous integrated gameplay, real-time sweep clock, DSP pitch publication '
        'or physical audio. Production ROM build flag remains unavailable/default disabled.')
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    bits=[('0','$4001 written','Pulse 1 sweep reload'),('1','$4005 written','Pulse 2 sweep reload'),
        ('2','$4002 written','Pulse 1 low timer'),('3','$4003 written','Pulse 1 high timer'),
        ('4','$4006 written','Pulse 2 low timer'),('5','$4007 written','Pulse 2 high timer'),
        ('6','$4017 written','Pending frame-clock reset'),('7','Last $4017 bit 7','Pending frame-clock mode')]
    table=''.join(f'<tr><td>{a}</td><td>{b}</td><td>{c}</td></tr>' for a,b,c in bits)
    (out/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>RCR sweep event transport</title>
<style>body{background:#101821;color:#eef;font:17px system-ui;max-width:1100px;margin:auto;padding:24px}
a{color:#9df}table{border-collapse:collapse}td,th{padding:9px;border:1px solid #567}.open{color:#ffd68b}</style>
<h1>Sweep write events now survive the tested transport components</h1>
<p>New default-disabled CPU hooks preserve sweep-control writes, separate low/high timer writes,
and frame-reset/mode events. Actual CPU generic/direct paths pass 6,144 cases; fused sound-commit
paths pass 4,096 cases, including suppressed music. ABI and other packet bytes match independent expectations.</p>
<p>The actual SPC paired receiver consumes each packet and echoes its acknowledgement tokens before
calling the new adapter, then the unchanged fast-reset handler. Receive slots start deliberately wrong,
so missing stores cannot accidentally pass. The existing duty helpers are also executed afterward.</p>
<p>57,344 metadata/reset/enable/duty cases and 1,024 delayed-sender cases pass. Delays of 16, 128,
1,024 and 2,048 SPC clocks are tested between packet groups. Untargeted direct-page state is checked.</p>
<h2>One byte, with explicit ownership</h2>
<p>Packet byte 20 becomes event metadata. SPC $54 holds it only during reception/extraction;
the adapter clears $54 before the existing fast-reset handler reuses it as its pending KON mask.
Packet size, acknowledgement tokens, legacy event flags and controller handling are unchanged.</p>
<table><tr><th>Bit</th><th>CPU event</th><th>SPC meaning</th></tr>'''+table+'''</table>
<p>Six executed broken variants are caught: dropped/wrong CPU event, uncleared metadata in the KON
slot, lost sweep reload, wrong high-timer source, and a missing receiver store. In the uncleared-slot
case, the actual duty helpers incorrectly suppress both key-ons; the test detects that sound-relevant failure.</p>
<p class="open">This metadata preserves which registers were written and the final mode, not timestamps,
multiplicity or arbitrary within-packet order. It does not claim cycle-exact original NES replay.</p>
<h2>Remaining before a playable candidate</h2>
<p>Connect a continuous half-frame clock and reset handling, route live sweep periods/muting to the DSP,
then run simultaneous CPU/SPC gameplay, speed/scrolling regressions and raw hardware-audio tests.
The intermediate test engine is not a finished sound driver and is not exposed by the normal ROM builder.</p>
<p class="open">No Rival deployment, controller input, restart or OBS change. No new audio/graphics capture
is presented. Combat sputtering and the full speed/scrolling/audio goal remain open.</p>
<p><a href="report.json">Bound sources and 36 CPU execution artifact sets</a> ·
<a href="../'''+producer.parent.name+'''/report.json">CPU cases</a> ·
<a href="../'''+receiver.parent.name+'''/report.json">SPC cases and actual KON observations</a> ·
<a href="../sweep-kernel-review-1086/">Executed sweep kernel</a> ·
<a href="../main-phase-rival-review-819/">Evidence hub</a></p></html>''')
    print(json.dumps(dict(dataset_verified=True,bindings=len(sources),verified_cpu_runs=len(roots))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('producer','receiver','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
