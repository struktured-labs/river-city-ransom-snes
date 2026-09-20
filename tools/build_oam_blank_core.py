"""Add explicit forced-blank spans to the existing read-only OAM observer."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha


def transform(source):
    old='\telse\n\t{\n\t\tconst uint16\tblack = BUILD_PIXEL(0, 0, 0);'
    if source.count(old)!=1 or "rcr_sprite_event('B'" in source:raise ValueError('Changed blank span insertion')
    return source.replace(old,"\telse\n\t{\n\t\trcr_sprite_event('B', 255);\n\t\tconst uint16\tblack = BUILD_PIXEL(0, 0, 0);")


def build(parent,out):
    if out.exists() or out.parent!=Path('.deps'):raise ValueError('Fresh .deps sibling required')
    proof=bound_report(parent/'sprite-event-build.json')
    if any(sha(parent/p)!=h for p,h in proof['artifacts'].items()):raise ValueError('Changed parent observer')
    sources=dict(proof['sources'])
    for p in (parent/'sprite-event-build.json',parent/'gfx.cpp',Path(__file__),Path('tests/test_oam_blank_core.py')):
        sources[str(p)]=sha(p)
    updated=transform((parent/'gfx.cpp').read_text())
    shutil.copytree(parent,out,ignore=shutil.ignore_patterns('.git','*.o','*.so','*.a'))
    (out/'gfx.cpp').write_text(updated)
    with (out/'oam-blank-build.log').open('w') as log:
        subprocess.run(['make','-j4','TARGET_NAME=rcr_oam_blank'],cwd=out/'libretro',stdout=log,stderr=subprocess.STDOUT,check=True)
    core=out/'libretro/rcr_oam_blank_libretro.so'
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Changed bound source')
    report=dict(core=str(core),core_sha256=sha(core),sources=sources,
        artifacts={str(p.relative_to(out)):sha(p) for p in (core,out/'gfx.cpp',out/'cpuexec.cpp',out/'dma.cpp',out/'oam-blank-build.log')},
        scope=__doc__+' B records the exact spans the existing renderer fills black. No emulated memory reads/writes, scheduling or output modifications.')
    (out/'sprite-event-build.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(core=str(core),sha256=sha(core))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):p.add_argument('--'+k,type=Path,required=True)
    build(**vars(p.parse_args()))
