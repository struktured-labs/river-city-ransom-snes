"""Build a sibling core with read-only source/prepared/actual-OAM event taps."""
import argparse
from pathlib import Path
import json
import shutil
import subprocess

from tools.benchmark_report import sha

ROOT = Path(__file__).resolve().parents[1]


def transform(name, source):
    if 'snes9x_sprite_' in source:
        raise ValueError('Already instrumented')
    edits = {
        'gfx.cpp': [('#include "../../tools/snes9x_background.inc"',
                     '#include "../../tools/snes9x_background.inc"\n#include "../../tools/snes9x_sprite_events.inc"'),
                    ('\t\tRenderScreen(FALSE);', '\t\trcr_sprite_event(\'R\', 255);\n\t\tRenderScreen(FALSE);')],
        'dma.cpp': [('bool8 S9xDoDMA (uint8 Channel)\n{',
                     'bool8 S9xDoDMA (uint8 Channel)\n{\n\t#include "../../tools/snes9x_sprite_dma.inc"')],
        'cpuexec.cpp': [('\t\t#include "../../tools/snes9x_cpu_profile.inc"',
                         '\t\t#include "../../tools/snes9x_sprite_cpu.inc"\n\t\t#include "../../tools/snes9x_cpu_profile.inc"')],
    }
    if name not in edits: raise ValueError('Unsupported source')
    for old, new in edits[name]:
        if source.count(old) != 1: raise ValueError('Changed observer insertion point')
        source = source.replace(old, new)
    return source


def build(parent, out):
    if out.exists() or out.resolve().parent != ROOT/'.deps':
        raise ValueError('Fresh .deps sibling required')
    files = [p for p in parent.rglob('*') if p.is_file() and '.git' not in p.parts and
        (p.suffix in {'.c', '.cpp', '.h', '.hpp', '.inc', '.S', '.s', '.mak', '.mk'} or p.name.startswith('Makefile'))]
    files += list((ROOT/'tools').glob('snes9x_*.inc'))+[Path(__file__), Path('tests/test_sprite_event_core.py')]
    sources = {str(p): sha(p) for p in files}
    changes = {name: transform(name, (parent/name).read_text()) for name in ('gfx.cpp', 'dma.cpp', 'cpuexec.cpp')}
    shutil.copytree(parent, out, ignore=shutil.ignore_patterns('.git', '*.o', '*.so', '*.a'))
    for name, text in changes.items(): (out/name).write_text(text)
    command = ['make', '-j4', 'TARGET_NAME=rcr_sprite_events']
    with (out/'sprite-build.log').open('w') as log:
        subprocess.run(command, cwd=out/'libretro', stdout=log, stderr=subprocess.STDOUT, check=True)
    if any(sha(Path(p)) != h for p, h in sources.items()): raise ValueError('Build source changed')
    core = out/'libretro/rcr_sprite_events_libretro.so'
    report = dict(core=str(core), core_sha256=sha(core), sources=sources, command=command,
        artifacts={str(p.relative_to(out)): sha(p) for p in [core, out/'sprite-build.log', *[out/n for n in changes]]},
        scope=__doc__+' Host reads only; no emulated register reads/writes. Fresh same-core controls required.')
    (out/'sprite-event-build.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(core=str(core), sha256=sha(core))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'out'): p.add_argument('--'+name, type=Path, required=True)
    build(**vars(p.parse_args()))
