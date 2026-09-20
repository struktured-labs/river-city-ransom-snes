"""Build a separate observer for every general-DMA envelope and actual PPU blank state."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.benchmark_report import sha

ROOT=Path(__file__).resolve().parents[1]


def transform(source):
    marker='bool8 S9xDoDMA (uint8 Channel)\n{'
    if source.count(marker)!=1:raise ValueError('Changed DMA insertion point')
    return source.replace(marker,marker+'\n\t#include "../../tools/snes9x_dma_safety.inc"')


def build(parent,out):
    if out.exists() or out.resolve().parent!=ROOT/'.deps':
        raise ValueError('Fresh sibling under .deps required')
    extensions={'.c','.cpp','.h','.hpp','.inc','.S','.s','.mak','.mk'}
    files=[p for p in parent.rglob('*') if p.is_file() and '.git' not in p.parts
           and (p.suffix in extensions or p.name.startswith('Makefile'))]
    files+=list((ROOT/'tools').glob('snes9x_*.inc'))+[Path(__file__)]
    sources={str(p):sha(p) for p in files}
    generated=transform((parent/'dma.cpp').read_text())
    shutil.copytree(parent,out,ignore=shutil.ignore_patterns('.git','*.o','*.so','*.a'))
    (out/'dma.cpp').write_text(generated)
    command=['make','-j4','TARGET_NAME=rcr_dma_safety']
    with (out/'build.log').open('w') as log:
        subprocess.run(command,cwd=out/'libretro',stdout=log,stderr=subprocess.STDOUT,check=True)
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Build source changed')
    core=out/'libretro/rcr_dma_safety_libretro.so'
    report=dict(core=str(core),core_sha256=sha(core),command=command,sources=sources,scope=__doc__,
        artifacts={str(p.relative_to(out)):sha(p) for p in (core,out/'dma.cpp',out/'build.log')})
    (out/'dma-safety-build.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(core=str(core),sha256=sha(core),sources=len(sources))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
