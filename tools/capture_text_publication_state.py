"""Read-only WRAM/VRAM windows around the audio trial's actual text differences."""
import argparse
import ctypes as C
import json
import os
from pathlib import Path
import time

from tools import benchmark_capture as bench
from tools.benchmark_report import sha,verify_capture
from tools.capture_combat_instructions import equivalent

WINDOWS=((5980,6030),(8232,8264))


def capture(candidate,core,normal,out):
    started=time.monotonic()
    if out.exists() or any(k.startswith('RCR_') for k in os.environ):raise ValueError('Fresh output and clean environment required')
    prior,rows0=verify_capture(normal)
    if prior['rom_sha256']!=sha(candidate/'native-cpu.sfc') or prior['core_sha256']!=sha(core):raise ValueError('Different control ROM/core')
    frames={f for a,b in WINDOWS for f in range(a,b+1)}
    if max(frames)>len(rows0):raise ValueError('Window outside control')
    paths=[Path(__file__),Path('tools/benchmark_capture.py'),Path('tools/benchmark_report.py'),
        Path('tools/capture_combat_instructions.py'),Path('tools/smoke_libretro.py'),core,
        candidate/'manifest.json',candidate/'native-cpu.sfc',normal/'capture.json',normal/'timeline.json',normal/'audio.wav']
    sources={str(p):sha(p) for p in paths}
    samples={};calls=0;original=C.CDLL
    def loader(path):
        nonlocal calls
        lib=original(path);run=lib.retro_run
        def step():
            nonlocal calls
            run();calls+=1
            if calls in frames:
                if lib.retro_get_memory_size(2)!=131072 or lib.retro_get_memory_size(3)!=65536:raise ValueError('Wrong direct WRAM/VRAM sizes')
                samples[calls]=C.string_at(lib.retro_get_memory_data(2),131072)+C.string_at(lib.retro_get_memory_data(3),65536)
        lib.retro_run=step
        return lib
    refs=dict(menu=(Path('build/reference-title-05'),600),settings=(Path('build/reference-walk-02'),600),
        story=(Path('build/reference-walk-02'),900),street=(Path('build/reference-walk-02'),1800))
    try:
        bench.C.CDLL=loader
        bench.capture(core,candidate/'native-cpu.sfc','snes',refs,out,'traversal-park-single-sweep',True,True)
    finally:
        bench.C.CDLL=original
    receipt,rows=verify_capture(out);equivalent(receipt,rows,prior,rows0)
    if set(samples)!=frames or calls!=len(rows):raise ValueError('Incomplete state windows')
    folder=out/'publication-states';folder.mkdir()
    artifacts={}
    for frame,state in samples.items():
        if state[:2048]!=bytes.fromhex(rows[frame-1]['game_ram_hex']):raise ValueError('Memory snapshot not at measured frame boundary')
        path=folder/f'{frame:05d}.bin';path.write_bytes(state)
        artifacts[str(frame)]=dict(path=str(path),sha256=sha(path))
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Changed capture source')
    sources[str(out/'capture.json')]=sha(out/'capture.json')
    sources[str(out/'timeline.json')]=sha(out/'timeline.json');sources[str(out/'audio.wav')]=sha(out/'audio.wav')
    sources.update({r['path']:r['sha256'] for r in artifacts.values()})
    report=dict(observer_neutral=True,frames=len(rows),windows=WINDOWS,samples=artifacts,
        layout=dict(wram=[0,131072],vram=[131072,196608]),candidate=str(candidate),normal=str(normal),
        elapsed_seconds=time.monotonic()-started,sources=sources,scope=__doc__+
        ' Post-retro_run direct memory copies, no emulated bus accesses or RAM edits. '
        'Complete same-core video/input/state/native PCM equality required.')
    (out/'publication-state.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(observer_neutral=True,frames=len(rows),snapshots=len(samples),seconds=report['elapsed_seconds'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','core','normal','out'):p.add_argument('--'+name,type=Path,required=True)
    capture(**vars(p.parse_args()))
