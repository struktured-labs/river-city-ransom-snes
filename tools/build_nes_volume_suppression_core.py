"""Build an opt-in, exact-clock NES volume-write suppression experiment."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.benchmark_report import sha

ROOT=Path(__file__).resolve().parents[1]


def transform(source):
    old='static INLINE void WrMemNorm(uint32_t A, uint8_t V) {\n    rcr_scroll_write(A, V);\n    #include "../../../tools/fceumm_apu_write_clock.inc"\n\tBWrite[A](A, V);\n}'
    if source.count(old)!=1:raise ValueError('Exact observed CPU dispatch changed')
    return source.replace(old,'#include "../../../tools/fceumm_volume_suppression.inc"\n'+
        old.replace('\tBWrite[A](A, V);','    if (!rcr_suppress_apu_write(A,V)) BWrite[A](A,V);'))


def build(parent,out):
    if out.exists() or out.resolve().parent!=ROOT/'.deps':raise ValueError('Fresh .deps sibling required')
    extensions={'.c','.cpp','.h','.hpp','.inc','.S','.s','.mak','.mk'}
    files=[p for p in parent.rglob('*') if p.is_file() and '.git' not in p.parts and
        (p.suffix in extensions or p.name.startswith('Makefile'))]
    files+=list((ROOT/'tools').glob('fceumm_*.inc'))+[Path(__file__)]
    sources={str(p):sha(p) for p in files}
    generated=transform((parent/'src/x6502.c').read_text())
    shutil.copytree(parent,out,ignore=shutil.ignore_patterns('.git','*.o','*.so','*.a'))
    (out/'src/x6502.c').write_text(generated)
    command=['make','-f','Makefile.libretro','-j4','TARGET_NAME=rcr_volume_suppress']
    with (out/'build.log').open('w') as log:subprocess.run(command,cwd=out,stdout=log,stderr=subprocess.STDOUT,check=True)
    core=out/'rcr_volume_suppress_libretro.so'
    for p,h in sources.items():
        if sha(Path(p))!=h:raise ValueError('Build source changed: '+p)
    result=dict(core=str(core),core_sha256=sha(core),command=command,sources=sources,
        artifacts={str(p.relative_to(out)):sha(p) for p in (core,out/'src/x6502.c',out/'build.log')},scope=__doc__)
    (out/'volume-suppression-build.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(core=str(core),sha256=sha(core),source_files=len(sources))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
