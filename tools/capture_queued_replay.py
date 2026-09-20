"""Add read-only per-frame queue accounting to a neutral restored instruction replay."""
import argparse
import ctypes as C
import json
import os
from pathlib import Path

from tools.replay_restored_instructions import capture
from tools.benchmark_report import sha


def run(**args):
    build=json.loads(args['core_build'].read_text());expected=Path(build['core']).resolve()
    original=C.CDLL;records=[];initial=[]
    def library(name,*a,**k):
        lib=original(name,*a,**k)
        if not isinstance(name,(str,bytes,os.PathLike)) or Path(os.fsdecode(name)).resolve()!=expected:return lib
        old=lib.retro_run
        getter=lib.retro_get_memory_data;getter.argtypes=[C.c_uint];getter.restype=C.c_void_p
        size=lib.retro_get_memory_size;size.argtypes=[C.c_uint];size.restype=C.c_size_t
        def read():
            ptr=getter(2)
            if not ptr or size(2)!=131072:raise ValueError('Missing full WRAM')
            ram=C.string_at(ptr,131072)
            return dict(pending=ram[0x1b87],collected=int.from_bytes(ram[0x1b88:0x1b8a],'little'),
                served=int.from_bytes(ram[0x1b8a:0x1b8c],'little'),overflow=ram[0x1b8c],
                native_id=int.from_bytes(ram[0x1c04:0x1c06],'little'),depth=ram[0x1c0a],
                original_busy=ram[0x107],completed=ram[0x52b])
        def step():
            if not records:initial.append(read())
            old();records.append(read())
        lib.retro_run=step
        return lib
    C.CDLL=library
    try:passed=capture(**args)
    finally:C.CDLL=original
    out=args['out'];path=out/'report.json';report=json.loads(path.read_text())
    if len(initial)!=1 or len(records)!=report['frames']:raise ValueError('Incomplete queue observations')
    for i,r in enumerate(records):r['frame']=report['restored_frame']+i+1
    state=dict(initial=initial[0],frames=records)
    (out/'queue.json').write_text(json.dumps(state,indent=2)+'\n')
    report['queue_accounting']=all(not r['overflow'] and ((r['collected']-r['served'])&65535)==r['pending']
                                   for r in [initial[0],*records])
    report['sources'].update({str(p):sha(p) for p in (Path(__file__),Path('tools/replay_restored_instructions.py'))})
    report['artifacts']['queue.json']=sha(out/'queue.json')
    path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(queue_accounting=report['queue_accounting'],initial=initial[0],final=records[-1])))
    return passed and report['queue_accounting']


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core-build','candidate','checkpoint-report','reference','out','control'):
        p.add_argument('--'+name,type=Path,required=True)
    for name in ('first','last'):p.add_argument('--'+name,type=int,required=True)
    raise SystemExit(0 if run(**vars(p.parse_args())) else 1)
