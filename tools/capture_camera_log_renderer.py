"""Actual scanline camera observation with exact complete replay qualification."""
import argparse
from contextlib import nullcontext
import json
import os
from pathlib import Path

from tools import benchmark_capture as benchmark
from tools.benchmark_report import sha, verify_capture
from tools.camera_state_log import seed_bytes
from tools.run_seeded_benchmark import seeded_core


def capture(candidate, core, normal, out, seeded=False):
    trace = out.with_suffix('.csv')
    if out.exists() or trace.exists() or any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Fresh process/output required')
    baseline, plain = verify_capture(normal)
    rom = candidate/'native-cpu.sfc'
    if (not baseline['capture_complete'] or baseline['rom_sha256'] != sha(rom)
            or baseline['scenario_name'] != 'traversal-park-single-sweep'
            or b'RCR_RENDER_SCROLL_TRACE' not in core.read_bytes()):
        raise ValueError('Need complete route, exact cartridge, renderer observer')
    paths = (Path(__file__), Path('tools/benchmark_capture.py'), Path('tools/benchmark_report.py'),
             Path('tools/smoke_libretro.py'), Path('tools/run_seeded_benchmark.py'),
             Path('tools/camera_state_log.py'), Path('tools/snes9x_raster_scroll.inc'),
             Path('.deps/snes9x-raster/gfx.cpp'), Path('.deps/snes9x-raster/libretro/libretro.cpp'),
             rom, candidate/'manifest.json', normal/'capture.json', core)
    sources = {str(p): sha(p) for p in paths}
    env = dict(RCR_RENDER_SCROLL_TRACE=str(trace.resolve()), RCR_RENDER_FIRST='1',
               RCR_RENDER_LAST=str(baseline['frames']))
    loaded = []
    refs = {'menu': (Path('build/reference-title-05'), 600),
            'settings': (Path('build/reference-walk-02'), 600),
            'story': (Path('build/reference-walk-02'), 900),
            'street': (Path('build/reference-walk-02'), 1800)}
    try:
        os.environ.update(env)
        with seeded_core(core, seed_bytes(), loaded) if seeded else nullcontext():
            benchmark.capture(core, rom, 'snes', refs, out, baseline['scenario_name'], True, True)
    finally:
        for key in env:
            os.environ.pop(key, None)
    receipt, rows = verify_capture(out)
    if (not receipt['capture_complete'] or rows != plain or any(
            receipt[k] != baseline[k] for k in ('rom_sha256', 'scenario_sha256', 'frames', 'audio_sha256'))
            or any(r['fault'] for r in rows)):
        raise ValueError('Renderer observer changed execution or incomplete/faulty route')
    if seeded and loaded != [dict(rom=str(rom.resolve()), rom_sha256=sha(rom),
                                   core=str(core.resolve()), core_sha256=sha(core))]:
        raise ValueError('Unexpected seeded load')
    if receipt['render_scroll_trace']['sha256'] != sha(trace) or not trace.stat().st_size:
        raise ValueError('Missing or changed renderer trace')
    if any(sha(Path(p)) != h for p, h in sources.items()):
        raise ValueError('Source changed during capture')
    for p in (trace, normal/'timeline.json', normal/'audio.wav',
              out/'capture.json', out/'timeline.json', out/'audio.wav'):
        sources[str(p)] = sha(p)
    report = dict(sources=sources, observer_neutral=True, seeded=seeded,
                  frames=len(rows), trace=str(trace), loaded=loaded,
                  scope='Every timeline field and native PCM equal the ordinary-core replay '
                  'of this same cartridge. Renderer observer neutrality does not establish '
                  'cartridge logger neutrality relative to uninstrumented gameplay.')
    (out/'renderer-observer.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(frames=len(rows), observer_neutral=True, seeded=seeded)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'core', 'normal', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--seeded', action='store_true')
    capture(**vars(p.parse_args()))
