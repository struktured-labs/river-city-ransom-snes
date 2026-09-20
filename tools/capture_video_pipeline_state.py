"""Read end-of-frame WRAM video stages plus the diagnostic background plane.

These are producer snapshots, not hardware OAM/CGRAM readback or atomic
publication events. Primary video, RAM, inputs and PCM must match the same-core
unobserved control exactly. No emulated writes or bus reads are performed.
"""
import argparse
from contextlib import contextmanager
import ctypes as C
import hashlib
import json
import os
from pathlib import Path

from tools import benchmark_capture as benchmark
from tools.benchmark_report import sha, verify_capture
from tools.capture_combat_instructions import equivalent
from tools.palette_telemetry import read as read_palette

REGIONS = {'game_oam': (0x200, 256), 'nes_oam_shadow': (0x1000, 256),
           'prepared_oam': (0x5000, 544), 'cached_oam_source': (0x5600, 256),
           'native_control': (0x1c00, 256)}


def read(pointer, size):
    if not pointer or size != 0x20000:
        raise ValueError('Expected full SNES WRAM')
    result = {k: C.string_at(pointer+start, count).hex()
              for k, (start, count) in REGIONS.items()}
    result['palette'] = read_palette(pointer, size)
    result['game_ram_sha256'] = hashlib.sha256(C.string_at(pointer, 2048)).hexdigest()
    return result


@contextmanager
def observe(core_path, frames):
    original = C.CDLL
    loaded = []
    expected = core_path.resolve()

    def library(name, *args, **kwargs):
        core = original(name, *args, **kwargs)
        if not isinstance(name, (str, bytes, os.PathLike)) or Path(os.fsdecode(name)).resolve() != expected:
            return core
        loaded.append(str(expected))
        run = core.retro_run

        def execute():
            run()
            frames.append(dict(frame=len(frames)+1,
                **read(core.retro_get_memory_data(2), core.retro_get_memory_size(2))))

        core.retro_run = execute
        return core

    C.CDLL = library
    try:
        yield
        if loaded != [str(expected)]:
            raise ValueError('Expected exactly one selected core load')
    finally:
        C.CDLL = original


def capture(core, candidate, normal, out):
    if out.exists() or any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Fresh output and clean instrumentation environment required')
    baseline, plain = verify_capture(normal)
    if baseline['rom_sha256'] != sha(candidate/'native-cpu.sfc') or baseline['core_sha256'] != sha(core):
        raise ValueError('Wrong same-core/ROM control')
    paths = [Path(__file__), Path('tests/test_video_pipeline_state.py'),
        Path('tools/palette_telemetry.py'), Path('tools/background_observer.py'),
        Path('tools/snes9x_background.inc'), core.parent.parent/'gfx.cpp',
        Path('tools/benchmark_capture.py'), Path('tools/benchmark_report.py'),
        Path('tools/capture_combat_instructions.py'), Path('tools/smoke_libretro.py'),
        core, candidate/'native-cpu.sfc', candidate/'manifest.json',
        normal/'capture.json', normal/'timeline.json', normal/'audio.wav']
    sources = {str(p): sha(p) for p in paths}
    frames = []
    refs = {'menu': (Path('build/reference-title-05'), 600),
            'settings': (Path('build/reference-walk-02'), 600),
            'story': (Path('build/reference-walk-02'), 900),
            'street': (Path('build/reference-walk-02'), 1800)}
    with observe(core, frames):
        benchmark.capture(core, candidate/'native-cpu.sfc', 'snes', refs, out,
            baseline['scenario_name'], True, True, background_telemetry=True)
    receipt, rows = verify_capture(out)
    equivalent(receipt, [{k: v for k, v in r.items() if k != 'background'} for r in rows], baseline, plain)
    if len(frames) != len(rows) or any(f['frame'] != r['frame'] or
        f['game_ram_sha256'] != hashlib.sha256(bytes.fromhex(r['game_ram_hex'])).hexdigest()
        for f, r in zip(frames, rows)):
        raise ValueError('End-of-frame state is not aligned with the primary timeline')
    (out/'video-stages.json').write_text(json.dumps(frames, separators=(',', ':'))+'\n')
    if any(sha(Path(p)) != h for p, h in sources.items()):
        raise ValueError('Changed source during capture')
    for name in ('capture.json', 'timeline.json', 'audio.wav', 'video-stages.json'):
        p = out/name; sources[str(p)] = sha(p)
    report = dict(rom_sha256=receipt['rom_sha256'], sources=sources, observer_neutral=True,
        frames=len(rows), control=str(normal), regions=REGIONS, scope=__doc__)
    (out/'video-stages-capture.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(frames=len(rows), observer_neutral=True)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('core', 'candidate', 'normal', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    capture(**vars(p.parse_args()))
