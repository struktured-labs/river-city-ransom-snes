"""Neutral first-room prefix with raw WRAM/VRAM snapshots across the CHR upload."""
import argparse
import ctypes as C
import json
from pathlib import Path
import time

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha,verify_capture
from tools.capture_combat_instructions import equivalent
from tools.capture_sprite_prefix import installed_prefix
from tools.capture_transition_prefix import capture as prefix


def capture(candidate,normal,out,first=2390,last=2450):
    started=time.monotonic()
    if out.exists() or not 1<=first<=last:raise ValueError('Fresh output and valid window required')
    control=bound_report(normal/'transition-prefix.json')
    with installed_prefix('right_08'):baseline,plain=verify_capture(normal)
    if not baseline['capture_complete'] or last>len(plain):raise ValueError('Incomplete baseline/window')
    core=Path('.deps/snes9x-raster/libretro/rcr_raster_libretro.so')
    if baseline['core_sha256']!=sha(core) or baseline['rom_sha256']!=sha(candidate/'native-cpu.sfc'):
        raise ValueError('Need same exact core and cartridge')
    sources=dict(control['sources']);sources[str(normal/'transition-prefix.json')]=sha(normal/'transition-prefix.json')
    for p in (Path(__file__),Path('tools/capture_transition_prefix.py'),Path('tools/capture_combat_instructions.py')):sources[str(p)]=sha(p)
    original=C.CDLL;loaded=[];samples=[]
    def loader(name,*args,**kwargs):
        lib=original(name,*args,**kwargs)
        if name is None or Path(name).resolve()!=core.resolve():return lib
        if loaded:raise ValueError('Multiple emulator instances')
        loaded.append(lib);run=lib.retro_run;frame=0
        def step():
            nonlocal frame
            run();frame+=1
            if not first<=frame<=last:return
            if lib.retro_get_memory_size(2)!=131072 or lib.retro_get_memory_size(3)!=65536:raise ValueError('Unexpected memory geometry')
            raw=C.string_at(lib.retro_get_memory_data(2),131072)+C.string_at(lib.retro_get_memory_data(3),65536)
            p=out/f'chr-state-{frame:05d}.bin';p.write_bytes(raw)
            samples.append(dict(frame=frame,path=str(p),sha256=sha(p)))
        lib.retro_run=step
        return lib
    try:
        C.CDLL=loader
        prefix(candidate,out)
    finally:C.CDLL=original
    with installed_prefix('right_08'):receipt,rows=verify_capture(out)
    equivalent(receipt,rows,baseline,plain)
    if [s['frame'] for s in samples]!=list(range(first,last+1)):raise ValueError('Missing snapshots')
    sources.update({s['path']:s['sha256'] for s in samples})
    for p in (out/'capture.json',out/'timeline.json',out/'audio.wav'):sources[str(p)]=sha(p)
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Changed observation dependency')
    report=dict(sources=sources,samples=samples,observer_neutral=True,first=first,last=last,
        frames=len(rows),normal=str(normal),candidate=str(candidate),seconds=time.monotonic()-started,
        scope=__doc__+' Full prefix video/input/state/native PCM equals same-core unobserved replay. '
        'No restored state or RAM writes. Raw131072-byte WRAM then65536-byte VRAM retained for each frame.')
    (out/'chr-state.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('observer_neutral','frames','first','last','seconds')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('candidate','normal','out'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--first',type=int,default=2390);p.add_argument('--last',type=int,default=2450)
    capture(**vars(p.parse_args()))
