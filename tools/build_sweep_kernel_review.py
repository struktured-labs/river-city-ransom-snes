"""Review actual executable sweep-kernel proof and small stateful examples."""
import argparse
import html
import json
from pathlib import Path

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.check_sweep_kernel import Runner


def build(proof,out):
    verified=bound_report(proof)
    if not verified['passed'] or verified['quick']:raise ValueError('Need complete executed proof')
    spc=Path('.deps/snes9x-kernel-1082/libretro/rcr_sweep_kernel_libretro.so')
    nes=Path('.deps/fceumm-kernel-1082/rcr_sweep_kernel_libretro.so')
    for p in (spc,nes):
        if verified['sources'].get(str(p))!=sha(p):raise ValueError('Unbound execution core')
    runner=Runner(spc,nes);examples={};tables=[]
    for title,initial,actions in (
        ('Repeated same-value sweep write reloads the divider',(0,172,0xa4,3,0),
            [('Same $4001 value',1,0xa4)]+[('Half-frame',0,0)]*4),
        ('Sweep between low/high timer writes is preserved',(1,144,0x84,1,0),
            [('Write $4006',2,144),('Half-frame',0,0),('Write $4007',3,0),('Half-frame',0,0)]),
        ('Disabled sweeps still advance the divider',(0,172,0x14,2,0),
            [('Half-frame',0,0)]*4)):
        runner.reset();runner.seed(*initial);rows=[];cells=[]
        for label,event,value in actions:
            actual,wanted=runner.event(initial[0],event,value)
            if actual[:4]!=wanted or actual[5]:raise ValueError('Example differs from actual NES function')
            rows.append(dict(label=label,event=event,value=value,spc=actual,nes=wanted))
            cells.append(f'<tr><td>{html.escape(label)}</td><td>{actual[0]}</td>'
                f'<td>{actual[2]}</td><td>{actual[3]}</td><td>{actual[4]}</td></tr>')
        examples[title]=dict(initial=initial,events=rows)
        tables.append(f'<h2>{html.escape(title)}</h2><p>Initial period {initial[1]}, '
            f'control ${initial[2]:02X}, countdown {initial[3]}, reload {initial[4]}.</p>'
            '<table><tr><th>Executed event</th><th>Period</th><th>Countdown</th>'
            '<th>Reload flag</th><th>SPC instruction clocks</th></tr>'+''.join(cells)+'</table>')
    out.mkdir(parents=True,exist_ok=False)
    report=dict(dataset_verified=True,release_ready=False,physical_audio_verified=False,
        examples=examples,sources={**verified['sources'],str(proof):sha(proof),
            str(Path(__file__)):sha(Path(__file__))},
        scope='Executable 304-byte SPC sweep-state kernel. Not yet connected to game transport, '
        'real-time half-frame clock or DSP publication. No new playable build or hardware restart.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>RCR executable sweep kernel</title>
<style>body{background:#101821;color:#eef;font:17px system-ui;max-width:1100px;margin:auto;padding:24px}
a{color:#9df}td,th{border:1px solid #567;padding:9px}table{border-collapse:collapse}.open{color:#ffd68b}</style>
<h1>New SPC sweep logic, executed against the NES reference</h1>
<p>A 304-byte experimental SPC700 implementation now handles half-frame sweep countdowns,
register-write reload flags, low/high timer writes, both subtraction rules, and positive overflow.
It does not infer writes from changes in final register values.</p>
<p>Actual SPC instructions match FCEUmm's actual <code>FrameSoundStuff</code> and
<code>Write_PSG</code> across <strong>8,388,608 independent cases</strong>, 82,080 stateful sequence
events, and all 43,343 relevant events in the previously observed NES replay. Zero mismatches.</p>
<p>Independent cases cover both voices, all 2,048 periods, all 256 controls, initial countdowns
0/1/2/8, and both reload states. Stateful sequences cover all countdowns 0–8, all eight dividers,
every timer byte, repeated identical writes, disable/re-enable, and interleaved low/high writes.
Untargeted direct-page state must remain unchanged.</p>
<p>Five executed broken variants are caught: frozen disabled divider, lost same-value reload,
wrong pulse-1 borrow, accepted positive overflow, and corrupting the other voice.
Half-frame entries take 31–244 instruction clocks in the independent matrix.
These are routine execution costs, not measured game-audio latency.</p>
<p class="open">Not connected to the game yet. A correct real-time clock, event-preserving packet
integration, and DSP output updates still need implementation and game/hardware verification.
This does not prove combat sputtering fixed, change gameplay speed or scrolling, or warrant a restart.</p>
<p>The examples below execute the new code and actual NES reference again; they are not
hand-drawn expected state diagrams.</p>'''+''.join(tables)+'''
<p><a href="report.json">Executed examples and source hashes</a> ·
<a href="../'''+proof.parent.name+'''/report.json">Full execution coverage and mutations</a> ·
<a href="../sweep-timing-review-1081/">Measured old scheduler mismatch</a> ·
<a href="../pulse-sweep-review-1070/">Earlier candidate screenshots and audio</a> ·
<a href="../main-phase-rival-review-819/">Evidence hub</a></p></html>''')
    print(json.dumps(dict(dataset_verified=True,bindings=len(report['sources']),examples=len(examples))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('proof','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
