"""Build a host-only complete pre-IRQ/post-RTI CPU-state observer."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import time
from tools.benchmark_report import sha

ROOT=Path(__file__).resolve().parents[1]


def transform(source):
    edits=[('static unsigned long long rcr_elapsed_line_clocks = 0;',
            'static unsigned long long rcr_elapsed_line_clocks = 0;\n#include "../../tools/snes9x_audio_irq_context.inc"'),
           ('\t\t\t\tS9xOpcode_IRQ();','\t\t\t\trcr_irq_context_begin();\n\t\t\t\tS9xOpcode_IRQ();'),
           ('\t\tRegisters.PCw++;\n\t\t(*Opcodes[Op].S9xOpcode)();',
            '\t\tconst bool rcr_context_return = rcr_irq_context_active && Registers.PCw == 0xf1d8 && Op == 0x40;\n'
            '\t\tRegisters.PCw++;\n\t\t(*Opcodes[Op].S9xOpcode)();\n'
            '\t\tif (rcr_context_return) rcr_irq_context_end();')]
    for old,new in edits:
        if source.count(old)!=1:raise ValueError('Changed IRQ observer insertion point')
        source=source.replace(old,new)
    return source


def build(parent,out):
    if out.exists() or out.resolve().parent!=ROOT/'.deps':raise ValueError('Fresh .deps sibling required')
    started=time.monotonic()
    extensions={'.c','.cpp','.h','.hpp','.inc','.S','.s','.mak','.mk'}
    files=[p for p in parent.rglob('*') if p.is_file() and '.git' not in p.parts and
           (p.suffix in extensions or p.name.startswith('Makefile'))]
    files+=list((ROOT/'tools').glob('snes9x_*.inc'))+[Path(__file__)]
    sources={str(p):sha(p) for p in files}
    generated=transform((parent/'cpuexec.cpp').read_text())
    shutil.copytree(parent,out,ignore=shutil.ignore_patterns('.git','*.o','*.so','*.a'))
    (out/'cpuexec.cpp').write_text(generated)
    command=['make','-j4','TARGET_NAME=rcr_irq_context']
    with (out/'build.log').open('w') as log:
        subprocess.run(command,cwd=out/'libretro',stdout=log,stderr=subprocess.STDOUT,check=True)
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Changed build source')
    core=out/'libretro/rcr_irq_context_libretro.so'
    report=dict(core=str(core),core_sha256=sha(core),command=command,sources=sources,
        seconds=time.monotonic()-started,scope=__doc__,
        artifacts={str(p.relative_to(out)):sha(p) for p in (core,out/'cpuexec.cpp',out/'build.log')})
    (out/'irq-context-build.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('core','core_sha256','seconds')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
