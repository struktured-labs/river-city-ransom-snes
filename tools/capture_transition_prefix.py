"""Fresh boot through right_08: first street transition, with optional renderer observation."""
import argparse
import json
import os
from pathlib import Path
import time

from tools import benchmark_capture as bench
from tools.benchmark_report import sha, verify_capture
from tools.capture_combat_instructions import equivalent
from tools.capture_sprite_prefix import installed_prefix


def capture(candidate,out,control=None):
    started=time.monotonic()
    core=Path('.deps/snes9x-raster/libretro/rcr_raster_libretro.so')
    trace=out.with_suffix('.csv')
    if out.exists() or trace.exists() or any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Fresh output and clean observer environment required')
    paths=[Path(__file__),Path('tools/benchmark_capture.py'),Path('tools/benchmark_report.py'),
           Path('tools/smoke_libretro.py'),Path('tools/capture_sprite_prefix.py'),
           Path('tools/capture_combat_instructions.py'),Path('tools/snes9x_raster_scroll.inc'),
           Path('.deps/snes9x-raster/gfx.cpp'),Path('.deps/snes9x-raster/libretro/libretro.cpp'),
           candidate/'native-cpu.sfc',candidate/'manifest.json',core]
    sources={str(p):sha(p) for p in paths}
    meta=json.loads((candidate/'manifest.json').read_text())
    if meta['rom_sha256']!=sha(candidate/'native-cpu.sfc'):raise ValueError('Changed cartridge')
    env={}
    if control:
        with installed_prefix('right_08'):baseline,plain=verify_capture(control)
        if baseline['core_sha256']!=sha(core) or baseline['rom_sha256']!=meta['rom_sha256']:
            raise ValueError('Need same-core same-ROM control')
        env=dict(RCR_RENDER_SCROLL_TRACE=str(trace.resolve()),RCR_RENDER_FIRST='1',RCR_RENDER_LAST=str(baseline['frames']))
    refs=dict(menu=(Path('build/reference-title-05'),600),settings=(Path('build/reference-walk-02'),600),
              story=(Path('build/reference-walk-02'),900),street=(Path('build/reference-walk-02'),1800))
    try:
        os.environ.update(env)
        with installed_prefix('right_08'):
            bench.capture(core,candidate/'native-cpu.sfc','snes',refs,out,'traversal-park-single-sweep',True,True)
            receipt,rows=verify_capture(out)
    finally:
        for k in env:os.environ.pop(k,None)
    if not receipt['capture_complete'] or any(r['fault'] or r['input_requested']!=r['input_delivered'] for r in rows):
        raise ValueError('Incomplete or faulty prefix')
    if control:
        equivalent(receipt,rows,baseline,plain)
        if sha(trace)!=receipt['render_scroll_trace']['sha256']:raise ValueError('Unbound renderer trace')
        sources.update({str(p):sha(p) for p in (trace,control/'capture.json',control/'timeline.json',control/'audio.wav')})
    sources.update({str(p):sha(p) for p in (out/'capture.json',out/'timeline.json',out/'audio.wav')})
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Source changed during replay')
    report=dict(sources=sources,observer_neutral=bool(control),control=str(control) if control else None,
                frames=len(rows),seconds=time.monotonic()-started,last_phase='right_08',
                scope=__doc__+' Full prefix video/state/input/native PCM equality required for observer pair. '
                'Not a full route, hardware, tile correctness, speed or acoustic fidelity qualification.')
    (out/'transition-prefix.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='sources'}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ('candidate','out'):parser.add_argument('--'+k,type=Path,required=True)
    parser.add_argument('--control',type=Path)
    capture(**vars(parser.parse_args()))
