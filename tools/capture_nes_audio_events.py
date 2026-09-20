"""Original NES sound-wrapper and main-loop clocks under the unchanged park traversal."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from tools.benchmark_report import sha, verify_capture
from tools.nes_event_trace import validate_file

POINTS={'0':'f27d','1':'f282','2':'f2da','3':'fa54','4':'fa64'}


def capture(core,normal,out):
    if out.exists() or any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Fresh capture and clean observer environment required')
    baseline,rows0=verify_capture(normal)
    rom=Path('roms/river-city-ransom-us.nes')
    if (baseline['system']!='nes' or baseline['scenario_name']!='traversal-park-single-sweep' or
        baseline['core_sha256']!=sha(core) or baseline['rom_sha256']!=sha(rom)):
        raise ValueError('Need same-core original NES route control')
    image=rom.read_bytes()
    # Fixed bank at $E000-$FFFF, from the authenticated US-ROM profile.
    if image[16+0x10000+0xfa54:16+0x10000+0xfa65]!=bytes.fromhex('adffbf48a90520d1fe2003806820d1fe60'):
        raise ValueError('Original sound wrapper differs')
    if b'RCR_NES_EVENT_TRACE' not in core.read_bytes():raise ValueError('Missing NES observer')
    trace=out.with_name(out.name+'-events.csv')
    if trace.exists():raise ValueError('Trace output exists')
    files=(Path(__file__),Path('tools/nes_event_trace.py'),Path('tools/fceumm_queue_trace.inc'),
        Path('.deps/fceumm-raster/src/x6502.c'),Path('tools/benchmark_capture.py'),Path('tools/smoke_libretro.py'),
        normal/'capture.json',normal/'timeline.json',normal/'audio.wav',rom,core)
    sources={str(p):sha(p) for p in files}
    env=dict(os.environ,RCR_NES_EVENT_TRACE=str(trace.resolve()),RCR_NES_TRACE_FIRST='1',
             RCR_NES_TRACE_LAST=str(baseline['frames']))
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
    validation=validate_file(trace,1,receipt['frames'],receipt['frames'],POINTS)
    for p in (trace,out/'capture.json',out/'timeline.json',out/'audio.wav'):
        sources[str(p)]=sha(p)
    for p,h in sources.items():
        if sha(Path(p))!=h:raise ValueError('Changed source: '+p)
    report=dict(observer_neutral=True,points=POINTS,trace=str(trace),sources=sources,validation=validation,
        scope='Actual original sound-wrapper entry/return and main/input/completion PCs. '
        'NES CPU cycles are not SNES master/SPC clocks. Same-core full input/RAM/video/PCM control; '
        'no game-memory patch, register-write replay or waveform fitting.')
    (out/'nes-audio-events.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(frames=len(rows),observer_neutral=True,validation=validation)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('core','normal','out'):p.add_argument('--'+k,type=Path,required=True)
    capture(**vars(p.parse_args()))
