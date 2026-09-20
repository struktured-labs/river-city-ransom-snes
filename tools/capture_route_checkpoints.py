"""Qualify checkpoint observation/roundtrip against an uninterrupted full route.

Diagnostic only. Historical instruction/span observers explicitly do not
support state restoration; all inherited RCR instrumentation is rejected.
"""
import argparse
import ctypes as C
import json
import os
from pathlib import Path

from tools import benchmark_capture as benchmark
from tools.benchmark_report import sha, verify_capture
from tools.capture_combat_instructions import equivalent


def checkpoint_frames(value, total):
    frames=[int(s) for s in value.split(',')]
    if not frames or frames!=sorted(set(frames)) or not 1<=frames[0]<=frames[-1]<total:
        raise ValueError('Need unique ascending checkpoint frames inside capture')
    return frames


def capture(core, candidate, normal, checkpoints, out, roundtrip=False):
    if out.exists():raise ValueError('Fresh output required')
    if any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Restoration is incompatible with historical trace counters')
    baseline,plain=verify_capture(normal)
    if baseline['scenario_name']!='traversal-park-single-sweep' or baseline['system']!='snes':
        raise ValueError('Need complete original full-route control')
    frames=checkpoint_frames(checkpoints,baseline['frames'])
    rom=candidate/'native-cpu.sfc'
    if sha(core)!=baseline['core_sha256'] or sha(rom)!=baseline['rom_sha256']:
        raise ValueError('Checkpoint core/ROM must equal normal control')
    paths=[Path(__file__),Path('tools/benchmark_capture.py'),Path('tools/smoke_libretro.py'),
        Path('tools/capture_combat_instructions.py'),Path('.deps/snes9x/libretro/libretro.cpp'),
        Path('.deps/snes9x/snapshot.cpp'),core,rom,candidate/'manifest.json',normal/'capture.json']
    sources={str(p):sha(p) for p in paths}
    snapshots=[];loaded=[];original=C.CDLL
    def loader(name,*args,**kwargs):
        lib=original(name,*args,**kwargs)
        if name is None or Path(name).resolve()!=core.resolve():return lib
        if loaded:raise ValueError('Multiple emulator instances in checkpoint process')
        loaded.append(lib)
        lib.retro_serialize_size.argtypes=[];lib.retro_serialize_size.restype=C.c_size_t
        for method in ('retro_serialize','retro_unserialize'):
            fn=getattr(lib,method);fn.argtypes=[C.c_void_p,C.c_size_t];fn.restype=C.c_bool
        run=lib.retro_run;frame=0
        def step():
            nonlocal frame
            run();frame+=1
            if frame not in frames:return
            size=lib.retro_serialize_size()
            if not 0<size<=16*1024*1024:raise ValueError('Invalid checkpoint size')
            buffer=C.create_string_buffer(size)
            if not lib.retro_serialize(buffer,size):raise ValueError('Core refused serialization')
            target=out/f'frame-{frame:05d}.savestate'
            target.write_bytes(buffer.raw)
            snapshots.append(dict(frame=frame,path=str(target),sha256=sha(target),bytes=size,
                roundtrip=roundtrip,source_frame_video_sha256=plain[frame-1]['video_sha256'],
                source_frame_ram_sha256=plain[frame-1]['ram_sha256']))
            if roundtrip and not lib.retro_unserialize(buffer,size):
                raise ValueError('Core refused same-ROM checkpoint restore')
        lib.retro_run=step
        return lib
    refs={'menu':(Path('build/reference-title-05'),600),
        'settings':(Path('build/reference-walk-02'),600),
        'story':(Path('build/reference-walk-02'),900),
        'street':(Path('build/reference-walk-02'),1800)}
    C.CDLL=loader
    try:
        benchmark.capture(core,rom,'snes',refs,out,baseline['scenario_name'],True,True)
    finally:
        C.CDLL=original
    receipt,rows=verify_capture(out)
    if [s['frame'] for s in snapshots]!=frames:raise ValueError('Missing requested checkpoints')
    if any(sha(Path(p))!=d for p,d in sources.items()):raise ValueError('Changed checkpoint source')
    sources[str(out/'capture.json')]=sha(out/'capture.json')
    sources.update({s['path']:s['sha256'] for s in snapshots})
    # Preserve structured rejection evidence rather than merely raising before reporting.
    error=None
    try:equivalent(receipt,rows,baseline,plain)
    except ValueError as exc:error=str(exc)
    result=dict(passed=error is None,error=error,checkpoints=snapshots,sources=sources,
        full_timeline_equal=rows==plain,full_pcm_equal=receipt['audio_sha256']==baseline['audio_sha256'],
        fresh_process_restore_verified=False,cross_rom_restore_verified=False,
        release_ready=False,scope='Same-process same-ROM checkpoint save or immediate roundtrip. '
        'Full uninterrupted controller policy and normal timeline/PCM must remain identical. '
        'Not cross-ROM resumed-game equivalence, a speed measurement, or physical testing.')
    (out/'checkpoint-report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('passed','error','full_timeline_equal','full_pcm_equal')}))
    return result['passed']


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','candidate','normal','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--checkpoints',required=True);p.add_argument('--roundtrip',action='store_true')
    raise SystemExit(0 if capture(**vars(p.parse_args())) else 1)
