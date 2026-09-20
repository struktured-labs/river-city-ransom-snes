"""Fresh-process sparse main/input/camera/finish observation for the current ROM."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from tools.benchmark_report import sha


def capture(candidate,core,out):
    trace=out.with_name(out.name+'.csv')
    if out.exists() or trace.exists():raise ValueError('Use fresh capture paths')
    labels=candidate/'native_runtime.lbl';rom=candidate/'native-cpu.sfc'
    symbols={s.split()[2].lstrip('.'):int(s.split()[1],16) for s in labels.read_text().splitlines()}
    points={0:symbols['gameplay_iteration_start'],1:0xf282,
            2:symbols['camera_deferred_nmi_exit']+2,3:0xf2da}
    image=rom.read_bytes()
    if image[0x10000+points[2]:0x10000+points[2]+2]!=bytes.fromhex('85f6'):
        raise ValueError('Unexpected camera store')
    paths=[Path(__file__),Path('tools/snes9x_main_store.inc'),Path('.deps/snes9x/cpuexec.cpp'),
        Path('tools/benchmark_capture.py'),Path('tools/smoke_libretro.py'),labels,rom,core]
    sources={str(p):sha(p) for p in paths}
    env=os.environ.copy();env['RCR_MAIN_STORE_TRACE']=str(trace.resolve())
    for i,pc in points.items():env[f'RCR_MAIN_STORE_PC{i}']=f'{pc:04x}'
    subprocess.run([sys.executable,'tools/benchmark_capture.py','--system','snes',
        '--core',str(core),'--rom',str(rom),'--title','build/reference-title-05',
        '--walk','build/reference-walk-02','--scenario','traversal-park-single-sweep',
        '--frame-images','--full-ram-telemetry','--out',str(out)],env=env,check=True)
    for p,digest in sources.items():
        if sha(Path(p))!=digest:raise ValueError('Source changed: '+p)
    if not trace.stat().st_size:raise ValueError('Missing sparse trace')
    path=out/'capture.json';receipt=json.loads(path.read_text())
    receipt['main_store_observer']=dict(sources=sources,points={str(k):f'{v:04x}' for k,v in points.items()},
        trace=dict(path=str(trace.resolve()),sha256=sha(trace)),
        scope='Only linked main start, input call, pre-STA F6 camera commit and F2DA completion. '
              'All host-only register/RAM observations, no emulated synchronization or state changes.')
    path.write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','core','out'):p.add_argument('--'+name,type=Path,required=True)
    capture(**vars(p.parse_args()))
