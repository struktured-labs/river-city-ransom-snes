"""Pair the original pause cue's source commands and scheduling, without retiming PCM."""
import argparse
import csv
import json
from pathlib import Path
import shutil
from tools.audit_main_display_latency import bound_report
from tools.audit_park_instructions import parse
from tools.benchmark_report import sha,verify_capture

ROOT=Path('build/overflow-3526')
NES_HZ=19687500/11
SNES_HZ=236250000/11


def envelope(events,request_pc,entry_pc,return_pc):
    if any(b['clock']<=a['clock'] for a,b in zip(events,events[1:])):
        raise ValueError('Nonmonotonic instruction events')
    requests=[e for e in events if e['pc']==request_pc]
    if len(requests)!=1:raise ValueError('Expected one isolated pause request')
    request=requests[0]
    entry=next((e for e in events if e['clock']>request['clock'] and e['pc']==entry_pc),None)
    if entry is None:raise ValueError('Missing subsequent driver entry')
    end=next((e for e in events if e['clock']>entry['clock'] and e['pc']==return_pc),None)
    if end is None:raise ValueError('Missing driver return')
    return dict(request=request,entry=entry,end=end,
        request_to_driver_clocks=entry['clock']-request['clock'],driver_clocks=end['clock']-entry['clock'])


def match_commands(nes,snes):
    if not nes or len(nes)!=len(snes) or nes!=snes:
        raise ValueError('Original source command order/value mismatch')
    return True


def audit(out):
    if out.exists():raise ValueError('Fresh output required')
    sources={}
    def proof(p):
        r=bound_report(p);sources.update(r['sources']);sources[str(p)]=sha(p);return r
    nes=proof(ROOT/'nes-pause-clock-observed-3653/pause-clock.json')
    snes=proof(ROOT/'empty-tail-pause-observed-3654/pause-observer.json')
    onset=proof(Path('build/paired-pause-onset-3655/report.json'))
    if not nes['observer_neutral'] or not snes['observer_neutral']:
        raise ValueError('Non-neutral observations')
    for normal,observed in (('nes-pause-clock-normal-3652','nes-pause-clock-observed-3653'),
                            ('empty-tail-status-3632','empty-tail-pause-observed-3654')):
        a,rows=verify_capture(ROOT/normal);b,other=verify_capture(ROOT/observed)
        if rows!=other or not a['capture_complete'] or any(a[k]!=b[k] for k in
                ('core_sha256','rom_sha256','frames','audio_sha256','scenario_sha256')):
            raise ValueError('Changed full execution/PCM or incomplete capture')
    events=[]
    for r in csv.reader(Path(nes['events']).open()):
        events.append(dict(frame=int(r[0]),line=int(r[1]),clock=int(r[2]),pc=int(r[4],16)))
    n=envelope(events,0xf7a8,0xfa54,0xfa64)
    with Path(snes['traces']['RCR_INSTRUCTION_TRACE']).open() as f:
        events=parse(csv.reader(f),snes['first'],snes['last'])
    s=envelope(events,0xc7f7a8,0xc1fa54,0xc7fa64)
    for result,hz in ((n,NES_HZ),(s,SNES_HZ)):
        result['request_to_driver_ms']=result['request_to_driver_clocks']*1000/hz
        result['driver_ms']=result['driver_clocks']*1000/hz
    nw=[r for r in csv.reader(Path(nes['writes']).open())
        if n['entry']['clock']<=int(r[1])<n['end']['clock']]
    all_sw=list(csv.reader(Path(snes['traces']['RCR_AUDIO_BUS_TRACE']).open()))
    first=next(r for r in all_sw if r[0]=='W' and int(r[1])==s['entry']['frame']
        and int(r[2])>=s['entry']['line'] and int(r[5])==4 and int(r[6])==240)
    sw=[r for r in all_sw if r[0]=='W' and r[4]==first[4]]
    commands_nes=[(int(r[3],16)-0x4000,int(r[4])) for r in nw]
    commands_snes=[(int(r[5]),int(r[6])) for r in sw]
    match_commands(commands_nes,commands_snes)
    bad=list(commands_snes);bad[-1]=(bad[-1][0],bad[-1][1]^1)
    try:match_commands(commands_nes,bad)
    except ValueError:mutant_rejected=True
    else:raise ValueError('Changed source command survived')
    if onset['passed']:raise ValueError('Expected retained onset failure')
    summary=dict(nes=n,snes=s,commands=commands_nes,source_commands_equal=True,
        additional_request_wait_ms=s['request_to_driver_ms']-n['request_to_driver_ms'],
        native_onset=dict(nes=onset['nes']['frame_offset'],snes=onset['snes']['frame_offset'],passed=False),
        changed_command_rejected=mutant_rejected)
    out.mkdir(parents=True)
    for name in ('nes.wav','snes.wav'):
        source=Path('build/paired-pause-onset-3655')/name
        sources[str(source)]=sha(source);shutil.copyfile(source,out/name)
        if sha(source)!=sha(out/name):raise ValueError('Changed native clip')
    body='''<!doctype html><meta charset="utf-8"><title>Original NES pause sound comparison</title>
<style>body{background:#101821;color:#eef;font:18px system-ui;max-width:1020px;margin:30px auto}
a{color:#9df}td,th{padding:10px;border-bottom:1px solid #456;text-align:left}audio{width:100%}</style>
<h1>The pause sound waits longer—not a slower original driver</h1>
<p>Fresh original NES and current3631 observations preserve each platform's entire same-core
video/input/state timeline and native PCM. This is diagnosis, not a new fix or deployment.</p>
<table><tr><th>Measured interval</th><th>Original NES</th><th>SNES3631</th></tr>'''
    body+=f'<tr><td>Pause sound request → driver entry</td><td>{n["request_to_driver_ms"]:.3f}ms</td><td>{s["request_to_driver_ms"]:.3f}ms</td></tr>'
    body+=f'<tr><td>Original sound wrapper execution</td><td>{n["driver_ms"]:.3f}ms</td><td>{s["driver_ms"]:.3f}ms</td></tr>'
    body+='''<tr><td>Source APU writes in this call</td><td colspan="2">Same seven ordered register/value writes</td></tr>
<tr><td>Native separated-sound onset</td><td>Input offset57</td><td>Offset58: still FAIL</td></tr></table>
<p>NES sets the cue during VBlank and services it near scanline31. The port sets it near line54 and
services it near256, with writes crossing into the next frame. The original wrapper itself runs
faster in this SNES observation; advancing or duplicating its music counters would not address the
measured wait. IRQ scheduling requires proper critical-section recovery: older raster experiments
lost timer events when adapters cleared hardware enables. Those failed experiments are not reused
as a working solution.</p>
<h2>Untouched native pause excerpts</h2><p>Original NES</p><audio controls src="nes.wav"></audio>
<p>Current SNES3631</p><audio controls src="snes.wav"></audio>
<p>Clocks use each core's declared NTSC rate; event timestamps are instruction-granular. There is
no cross-platform frame-number or sample alignment, normalization or resampling. Source-command
equality does not prove DSP/analog waveform equivalence. This explains the measured pause latency,
not every physical pop, and does not certify original-game speed.</p>
<p><a href="report.json">Exact clock events, command rows, controls and source bindings</a></p>'''
    (out/'index.html').write_text(body)
    for p in (Path(__file__),Path('tests/test_paired_pause_clock.py'),
              Path('.deps/fceumm-apu-clock-3130/src/x6502.h'),Path('.deps/snes9x-voice-2292/snes9x.h'),
              Path('docs/RASTER-WORKER-EXPERIMENT.md'),Path('snes/interrupt_policy.inc')):
        sources[str(p)]=sha(p)
    for p,h in sources.items():
        if sha(Path(p))!=h:raise ValueError('Changed source')
    report=dict(summary=summary,nes_write_rows=nw,snes_write_rows=sw,sources=sources,
        artifacts={p.name:sha(p) for p in out.iterdir()},fix_verified=False,release_ready=False,
        physical_verified=False,scope=__doc__)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(summary))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    audit(**vars(p.parse_args()))
