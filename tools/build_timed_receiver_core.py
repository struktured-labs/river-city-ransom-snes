"""Add automatic-commit fixture observations to the qualified staged test core."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import time
from tools.benchmark_report import sha
from tools.review_command_priority import bound


def build(parent,out):
    if out.exists() or out.parent!=Path('.deps'):raise ValueError('Fresh .deps sibling required')
    bound(parent/'staged-core.json')
    src=parent/'apu/bapu/smp/smp.cpp';original=src.read_text()
    anchor='#include "../../../../../tools/spc_staged_receiver_probe.inc"'
    if original.count(anchor)!=1:raise ValueError('Changed probe anchor')
    paths=[Path(__file__),Path('tools/spc_timed_receiver_probe.inc'),parent/'staged-core.json']
    paths += [p for p in parent.rglob('*') if p.is_file() and p.suffix in ('.cpp','.h','.hpp','.inc')]
    sources={str(p):sha(p) for p in paths};start=time.monotonic()
    shutil.copytree(parent,out,ignore=shutil.ignore_patterns('.git','*.o','*.so','*.a'))
    (out/'apu/bapu/smp/smp.cpp').write_text(original.replace(anchor,anchor+'\n#include "../../../../../tools/spc_timed_receiver_probe.inc"'))
    with (out/'build.log').open('w') as log:
        subprocess.run(['make','-j4','TARGET_NAME=rcr_timed_receiver'],cwd=out/'libretro',stdout=log,stderr=subprocess.STDOUT,check=True)
    core=out/'libretro/rcr_timed_receiver_libretro.so'
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Changed source')
    report=dict(core=str(core),sources=sources,artifacts={str(p.relative_to(out)):sha(p) for p in (core,out/'apu/bapu/smp/smp.cpp',out/'build.log')},
        seconds=time.monotonic()-start,fixture_only=True,scope=__doc__)
    (out/'timed-core.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(core=str(core),seconds=report['seconds'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):p.add_argument('--'+k,type=Path,required=True)
    build(**vars(p.parse_args()))
