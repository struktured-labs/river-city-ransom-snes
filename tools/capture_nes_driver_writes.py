"""Observe original APU writes and sound-wrapper boundaries with a same-core control."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha,verify_capture
from tools.capture_nes_audio_events import POINTS
from tools.nes_event_trace import validate_file


def capture(core,normal,out):
    if out.exists() or any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Fresh output and clean observer environment required')
    build=bound_report(core.parent/'apu-clock-build.json')
    if build['core_sha256']!=sha(core):raise ValueError('Unbound observer core')
    baseline,rows0=verify_capture(normal)
    rom=Path('roms/river-city-ransom-us.nes')
    if (baseline['system']!='nes' or baseline['scenario_name']!='traversal-park-single-sweep' or
        baseline['core_sha256']!=sha(core) or baseline['rom_sha256']!=sha(rom)):
        raise ValueError('Need same-core original NES route control')
    if rom.read_bytes()[16+0x10000+0xfa54:16+0x10000+0xfa65]!=bytes.fromhex('adffbf48a90520d1fe2003806820d1fe60'):
        raise ValueError('Original sound wrapper differs')
    events=out.with_name(out.name+'-events.csv');writes=out.with_name(out.name+'-writes.csv')
    if events.exists() or writes.exists():raise ValueError('Trace output exists')
    sources={**build['sources'],**{str(p):sha(p) for p in (Path(__file__),
        Path('tools/capture_nes_audio_events.py'),Path('tools/nes_event_trace.py'),
        Path('tools/fceumm_apu_write_clock.inc'),Path('tools/benchmark_capture.py'),
        Path('tools/smoke_libretro.py'),core.parent/'apu-clock-build.json',
        normal/'capture.json',normal/'timeline.json',normal/'audio.wav',rom,core)}}
    env=dict(os.environ,RCR_NES_EVENT_TRACE=str(events.resolve()),RCR_NES_TRACE_FIRST='1',
        RCR_NES_TRACE_LAST=str(baseline['frames']),RCR_NES_APU_WRITE_CLOCK=str(writes.resolve()))
    env.update({f'RCR_NES_EVENT_PC{k}':v for k,v in POINTS.items()})
    command=[sys.executable,'-m','tools.benchmark_capture','--system','nes','--core',str(core),
        '--rom',str(rom),'--title','build/reference-title-05','--walk','build/reference-walk-02',
        '--scenario','traversal-park-single-sweep','--frame-images','--full-ram-telemetry','--out',str(out)]
    if 'nes_ppu_observer' in baseline:command.append('--ppu-telemetry')
    subprocess.run(command,env=env,check=True)
    receipt,rows=verify_capture(out)
    if rows!=rows0 or not receipt['capture_complete'] or any(receipt[k]!=baseline[k] for k in
        ('system','core_sha256','rom_sha256','scenario_sha256','frames','audio_sha256')):
        raise ValueError('NES observer changed full execution or PCM')
    validation=validate_file(events,1,receipt['frames'],receipt['frames'],POINTS)
    if not writes.is_file() or not writes.stat().st_size:raise ValueError('Missing APU writes')
    for p in (events,writes,out/'capture.json',out/'timeline.json',out/'audio.wav'):
        sources[str(p)]=sha(p)
    for p,h in sources.items():
        if sha(Path(p))!=h:raise ValueError('Changed source: '+p)
    result=dict(observer_neutral=True,points=POINTS,events=str(events),writes=str(writes),
        sources=sources,validation=validation,scope=__doc__+
        ' Host-only CPU-store observation before BWrite, instruction-granular CPU clock. '
        'No emulated access, cycle addition, waveform fitting or register replay.')
    (out/'driver-writes.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(frames=len(rows),observer_neutral=True,validation=validation)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','normal','out'):p.add_argument('--'+name,type=Path,required=True)
    capture(**vars(p.parse_args()))
