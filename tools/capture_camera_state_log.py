"""Capture a seeded camera diagnostic plus SRAM without changing emulated state mid-run."""
import argparse
import ctypes as C
import json
import os
from pathlib import Path

from tools import benchmark_capture as benchmark
from tools.benchmark_report import sha, verify_capture
from tools.camera_state_log import decode, seed_bytes
from tools.run_seeded_benchmark import seeded_core


def capture(candidate,core,out,scenario='pause-status'):
    if out.exists() or any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Fresh uninstrumented capture environment required')
    rom=candidate/'native-cpu.sfc';seed=candidate/'seed.srm'
    meta=json.loads((candidate/'manifest.json').read_text())
    if sha(rom)!=meta['rom_sha256'] or seed.read_bytes()!=seed_bytes():
        raise ValueError('Wrong diagnostic or seed')
    paths=(Path(__file__),Path('tools/camera_state_log.py'),Path('tools/run_seeded_benchmark.py'),
        Path('tools/benchmark_capture.py'),Path('tools/smoke_libretro.py'),
        rom,core,seed,candidate/'manifest.json')
    sources={str(p):sha(p) for p in paths}
    loaded=[];frames=[];saved=[]
    with seeded_core(core,seed.read_bytes(),loaded):
        original=C.CDLL
        def library(name,*args,**kwargs):
            lib=original(name,*args,**kwargs)
            if not isinstance(name,(str,bytes,os.PathLike)) or Path(os.fsdecode(name)).resolve()!=core.resolve():
                return lib
            step=lib.retro_run;unload=lib.retro_unload_game
            def memory(kind,size):
                pointer=lib.retro_get_memory_data(kind)
                if not pointer or lib.retro_get_memory_size(kind)!=size:
                    raise ValueError('Unexpected libretro memory mapping')
                return C.string_at(pointer,size)
            def run():
                step()
                ram=memory(0,131072)
                frames.append(dict(frame=len(frames)+1,total=int.from_bytes(ram[8:12],'little'),
                                   header=ram[:32].hex()))
            def finish():
                try:
                    data=memory(0,131072)
                    (out/'camera.srm').write_bytes(data)
                    saved.append(decode(data))
                finally:
                    unload()
            lib.retro_run=run;lib.retro_unload_game=finish
            return lib
        C.CDLL=library
        refs={'menu':(Path('build/reference-title-05'),600),'settings':(Path('build/reference-walk-02'),600),
              'story':(Path('build/reference-walk-02'),900),'street':(Path('build/reference-walk-02'),1800)}
        try:
            benchmark.capture(core,rom,'snes',refs,out,scenario,True,True)
        finally:
            C.CDLL=original
    receipt,rows=verify_capture(out)
    if loaded!=[dict(rom=str(rom.resolve()),rom_sha256=sha(rom),core=str(core.resolve()),core_sha256=sha(core))] or len(saved)!=1:
        raise ValueError('Expected one authenticated seeded load and export')
    if any(sha(Path(p))!=h for p,h in sources.items()):
        raise ValueError('Source changed during capture')
    records=saved[0]
    (out/'camera.json').write_text(json.dumps(records,indent=2)+'\n')
    (out/'camera-frames.json').write_text(json.dumps(frames,indent=2)+'\n')
    sources.update({str(out/name):sha(out/name) for name in ('camera.srm','camera.json',
        'camera-frames.json','capture.json','timeline.json','audio.wav')})
    report=dict(loaded=loaded,sources=sources,records=records['total'],
        timeouts=sum(r['timeout'] for r in records['records']),
        changed_nmi_during_record=sum(r['nmi_changed_during_record'] for r in records['records']),
        timing_neutral_verified=False,physical_deployed=False,
        scope='Host seeds exact SRAM once before first run; exports at unload. Logger adds emulated CPU work. '
              'Successful decoding is not timing-neutrality or actual displayed-PPU validation.')
    (out/'logger-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('records','timeouts','changed_nmi_during_record')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','core','out'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--scenario',default='pause-status')
    capture(**vars(p.parse_args()))
