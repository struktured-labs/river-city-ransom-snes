"""Original pause cue, sound-wrapper, and APU-write timing with full neutral control."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha,verify_capture
from tools.nes_event_trace import validate_file

POINTS={'0':'f27d','1':'f282','2':'f2da','3':'fa54','4':'fa64','5':'f799','6':'f7a8'}


def capture(core,normal,out):
    if out.exists() or any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Fresh output and clean observer environment required')
    build=bound_report(core.parent/'apu-clock-build.json')
    if sha(core)!=build['core_sha256']:raise ValueError('Changed observer core')
    baseline,old=verify_capture(normal);rom=Path('roms/river-city-ransom-us.nes')
    if (baseline['system']!='nes' or not baseline['capture_complete']
            or baseline['scenario_name']!='pause-status' or baseline['core_sha256']!=sha(core)
            or baseline['rom_sha256']!=sha(rom)):
        raise ValueError('Need same-core complete original pause control')
    first_pause=next(r['frame'] for r in old if r['phase']=='pause_open')
    first=first_pause+50;last=first_pause+65
    image=rom.read_bytes()
    for at,expected in ((0xfa54,'adffbf48a90520d1fe2003806820d1fe60'),
                        (0xf799,'853fa9018dd006207df3a9008dd0062089f3')):
        blob=bytes.fromhex(expected)
        if image[16+0x10000+at:16+0x10000+at+len(blob)]!=blob:
            raise ValueError('Changed original fixed-bank event site')
    events=out.with_name(out.name+'-events.csv');writes=out.with_name(out.name+'-writes.csv')
    if events.exists() or writes.exists():raise ValueError('Trace output exists')
    sources=dict(build['sources'])
    for p in (Path(__file__),Path('tools/nes_event_trace.py'),Path('tools/benchmark_capture.py'),
              Path('tools/benchmark_report.py'),Path('tools/smoke_libretro.py'),
              core.parent/'apu-clock-build.json',core,rom,normal/'capture.json',
              normal/'timeline.json',normal/'audio.wav'):
        sources[str(p)]=sha(p)
    env=dict(os.environ,RCR_NES_EVENT_TRACE=str(events.resolve()),RCR_NES_TRACE_FIRST=str(first),
        RCR_NES_TRACE_LAST=str(last),RCR_NES_APU_WRITE_CLOCK=str(writes.resolve()))
    env.update({f'RCR_NES_EVENT_PC{k}':v for k,v in POINTS.items()})
    start=time.monotonic()
    subprocess.run([sys.executable,'-m','tools.benchmark_capture','--system','nes','--core',str(core),
        '--rom',str(rom),'--title','build/reference-title-05','--walk','build/reference-walk-02',
        '--scenario','pause-status','--frame-images','--full-ram-telemetry','--out',str(out)],env=env,check=True)
    elapsed=time.monotonic()-start
    receipt,rows=verify_capture(out)
    if rows!=old or not receipt['capture_complete'] or any(receipt[k]!=baseline[k] for k in
            ('rom_sha256','core_sha256','scenario_sha256','frames','audio_sha256')):
        raise ValueError('Observer changed complete execution or native PCM')
    validation=validate_file(events,first,last,receipt['frames'],POINTS)
    if not writes.stat().st_size:raise ValueError('Missing APU writes')
    for p in (events,writes,out/'capture.json',out/'timeline.json',out/'audio.wav'):sources[str(p)]=sha(p)
    for p,h in sources.items():
        if sha(Path(p))!=h:raise ValueError('Changed source: '+p)
    report=dict(observer_neutral=True,points=POINTS,first=first,last=last,events=str(events),
        writes=str(writes),sources=sources,validation=validation,capture_wall_seconds=elapsed,
        scope=__doc__+' Host-only instruction-granular clocks; no emulated state or input changes.')
    (out/'pause-clock.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(observer_neutral=True,frames=len(rows),validation=validation,seconds=elapsed)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('core','normal','out'):p.add_argument('--'+k,type=Path,required=True)
    capture(**vars(p.parse_args()))
