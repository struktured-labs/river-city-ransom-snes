"""Read-only per-frame shadow/stage/VRAM observations for HUD and dialogue rows."""
import argparse
import ctypes as C
import json
import os
from pathlib import Path
import time

from tools import benchmark_capture as bench
from tools.benchmark_report import sha, verify_capture
from tools.capture_combat_instructions import equivalent

ROWS = (2, 25)


def capture(candidate, core, normal, out):
    started = time.monotonic()
    if out.exists() or any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Fresh output and clean environment required')
    prior, control = verify_capture(normal)
    if prior['rom_sha256'] != sha(candidate/'native-cpu.sfc') or prior['core_sha256'] != sha(core):
        raise ValueError('Wrong control')
    paths = [Path(__file__), Path('tools/benchmark_capture.py'), Path('tools/benchmark_report.py'),
             Path('tools/capture_combat_instructions.py'), Path('tools/smoke_libretro.py'),
             core, candidate/'manifest.json', candidate/'native-cpu.sfc', normal/'capture.json',
             normal/'timeline.json', normal/'audio.wav']
    sources = {str(p): sha(p) for p in paths}
    original = C.CDLL
    samples = []

    def loader(path):
        lib = original(path)
        run = lib.retro_run

        def step():
            run()
            if lib.retro_get_memory_size(2) != 131072 or lib.retro_get_memory_size(3) != 65536:
                raise ValueError('Wrong direct memory layout')
            wram, vram = lib.retro_get_memory_data(2), lib.retro_get_memory_data(3)
            rows = {}
            for r in ROWS:
                rows[str(r)] = dict(shadow=C.string_at(wram+0x12000+r*32, 32).hex(),
                    staged=C.string_at(wram+0x3000+r*64, 64).hex(),
                    vram=C.string_at(vram+0x4000+r*64, 64).hex())
            samples.append(dict(frame=len(samples)+1, flags=C.string_at(wram+0x1D00, 128).hex(), rows=rows))

        lib.retro_run = step
        return lib

    refs = dict(menu=(Path('build/reference-title-05'), 600), settings=(Path('build/reference-walk-02'), 600),
                story=(Path('build/reference-walk-02'), 900), street=(Path('build/reference-walk-02'), 1800))
    try:
        bench.C.CDLL = loader
        bench.capture(core, candidate/'native-cpu.sfc', 'snes', refs, out, 'traversal-park-single-sweep', True, True)
    finally:
        bench.C.CDLL = original
    receipt, rows = verify_capture(out)
    equivalent(receipt, rows, prior, control)
    if len(samples) != len(rows):
        raise ValueError('Missing row observation')
    for sample, row in zip(samples, rows):
        if sample['frame'] != row['frame'] or sample['flags'] != row['native']['row_flags_hex']:
            raise ValueError('Incorrect snapshot frame boundary')
    if any(sha(Path(p)) != h for p, h in sources.items()):
        raise ValueError('Changed source')
    path = out/'row-publication.json'
    path.write_text(json.dumps(samples)+'\n')
    for p in (path, out/'capture.json', out/'timeline.json', out/'audio.wav'):
        sources[str(p)] = sha(p)
    report = dict(observer_neutral=True, frames=len(rows), rows=ROWS, sources=sources,
                  samples=str(path), seconds=time.monotonic()-started,
                  scope=__doc__+' Every sample follows retro_run. No bus accesses or writes; '
                  'full same-core primary timeline and native PCM must match. First nametable only; '
                  'tile interpretation requires scene/mirroring checks in the audit.')
    (out/'row-observer.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(observer_neutral=True, frames=len(rows), seconds=report['seconds'])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for k in ('candidate', 'core', 'normal', 'out'):
        p.add_argument('--'+k, type=Path, required=True)
    capture(**vars(p.parse_args()))
