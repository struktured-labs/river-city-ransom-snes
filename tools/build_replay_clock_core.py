"""Build a separate Snes9x observer with an explicitly reset post-restore clock."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.benchmark_report import sha

ROOT = Path(__file__).resolve().parents[1]


def transform(source):
    edits = (
        ('static unsigned long long rcr_elapsed_line_clocks = 0;',
         'static unsigned long long rcr_elapsed_line_clocks = 0;\n#include "../../tools/snes9x_replay_clock.inc"'),
        ('\t\tuint8\t\t\t\tOp;', '\t\trcrReplayInstruction();\n\t\tuint8\t\t\t\tOp;'),
        ('\t\t\trcr_elapsed_line_clocks += Timings.H_Max;',
         '\t\t\trcrReplayLine();\n\t\t\trcr_elapsed_line_clocks += Timings.H_Max;'))
    for old,new in edits:
        if source.count(old) != 1:
            raise ValueError('Changed core instrumentation insertion point')
        source = source.replace(old,new)
    return source


def build(parent,out):
    if out.exists() or out.resolve().parent != ROOT/'.deps':
        raise ValueError('Fresh sibling under .deps required for relative includes')
    extensions = {'.c','.cpp','.h','.hpp','.inc','.S','.s','.mak','.mk'}
    files = [p for p in parent.rglob('*') if p.is_file() and '.git' not in p.parts
             and (p.suffix in extensions or p.name.startswith('Makefile'))]
    files += list((ROOT/'tools').glob('snes9x_*.inc'))
    files += [Path(__file__)]
    sources = {str(p):sha(p) for p in files}
    generated = transform((parent/'cpuexec.cpp').read_text())
    shutil.copytree(parent,out,ignore=shutil.ignore_patterns('.git','*.o','*.so','*.a'))
    (out/'cpuexec.cpp').write_text(generated)
    command = ['make','-j4','TARGET_NAME=rcr_replay_clock']
    with (out/'build.log').open('w') as log:
        subprocess.run(command,cwd=out/'libretro',stdout=log,stderr=subprocess.STDOUT,check=True)
    if any(sha(Path(p)) != digest for p,digest in sources.items()):
        raise ValueError('Build input changed')
    core = out/'libretro/rcr_replay_clock_libretro.so'
    report = dict(core=str(core),core_sha256=sha(core),command=command,sources=sources,
        generated_cpuexec_sha256=sha(out/'cpuexec.cpp'),scope=__doc__,
        artifacts={str(p.relative_to(out)):sha(p) for p in (core,out/'cpuexec.cpp',out/'build.log')})
    (out/'replay-clock-build.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(core=str(core),sha256=sha(core),sources=len(sources))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):
        p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
