"""Expose actual CGRAM through a read-only host memory query, without emulated bus reads."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
from tools.benchmark_report import sha

ROOT=Path(__file__).resolve().parents[1]
MEMORY_ID=0x5243


def transform(source):
    data='''        case RETRO_MEMORY_VIDEO_RAM:
        data = Memory.VRAM;
        break;'''
    size='''        case RETRO_MEMORY_VIDEO_RAM:
            size = 64 * 1024;
            break;'''
    if source.count(data)!=1 or source.count(size)!=1:
        raise ValueError('Changed libretro memory API')
    return source.replace(data,data+'''
        case 0x5243:
            static_assert(sizeof(PPU.CGDATA) == 512, "Unexpected CGRAM size");
            data = PPU.CGDATA;
            break;''').replace(size,size+'''
        case 0x5243:
            size = sizeof(PPU.CGDATA);
            break;''')


def build(parent,out):
    if out.exists() or out.resolve().parent!=ROOT/'.deps':raise ValueError('Fresh sibling under .deps required')
    extensions={'.c','.cpp','.h','.hpp','.inc','.S','.s','.mak','.mk'}
    files=[p for p in parent.rglob('*') if p.is_file() and '.git' not in p.parts and
           (p.suffix in extensions or p.name.startswith('Makefile'))]
    parent_core=parent/'libretro/rcr_voice_edge_libretro.so'
    files+=list((ROOT/'tools').glob('snes9x_*.inc'))+[Path(__file__),parent_core]
    sources={str(p):sha(p) for p in files}
    generated=transform((parent/'libretro/libretro.cpp').read_text())
    shutil.copytree(parent,out,ignore=shutil.ignore_patterns('.git','*.o','*.so','*.a'))
    (out/'libretro/libretro.cpp').write_text(generated)
    command=['make','-j4','TARGET_NAME=rcr_cgram_read']
    with (out/'build.log').open('w') as log:
        subprocess.run(command,cwd=out/'libretro',stdout=log,stderr=subprocess.STDOUT,check=True)
    if any(sha(p)!=h for p,h in sources.items()):raise ValueError('Changed source during build')
    core=out/'libretro/rcr_cgram_read_libretro.so'
    report=dict(sources=sources,core=str(core),core_sha256=sha(core),parent_core_sha256=sha(parent_core),
        memory_id=MEMORY_ID,command=command,scope=__doc__,
        artifacts={str(p.relative_to(out)):sha(p) for p in (core,out/'libretro/libretro.cpp',out/'build.log')})
    (out/'cgram-build.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(core=str(core),sha256=sha(core))))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):parser.add_argument('--'+k,type=Path,required=True)
    build(**vars(parser.parse_args()))
