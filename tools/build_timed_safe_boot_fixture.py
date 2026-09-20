"""Keep DSP echo writes disabled throughout legacy register initialization."""
import argparse
import json
from pathlib import Path
from tools.build_sweep_kernel import Program
from tools.review_command_priority import bound
from tools.benchmark_report import sha


def build(parent,out):
    if out.exists():raise ValueError('Fresh output required')
    meta=bound(parent/'manifest.json');b=bytearray((parent/'engine.bin').read_bytes())
    if sha(parent/'engine.bin')!=meta['engine_sha256']:raise ValueError('Changed engine')
    at=0xbc7-0x400
    if b[at:at+4]!=bytes.fromhex('c4f2cbf3'):raise ValueError('Changed DSP clearing loop')
    p=Program(0x36c0);p.put(0xc4,0xf2,0x68,0x6c);p.when(0xd0,'ordinary')
    p.put(0x8f,0x20,0xf3,0x5f,0xcb,0x0b)
    p.label('ordinary');p.put(0xcb,0xf3,0x5f,0xcb,0x0b)
    code,_=p.result();b[at:at+4]=bytes.fromhex('5fc03600')
    if len(b)>0x36c0-0x400:raise ValueError('Occupied helper')
    b.extend(bytes(0x36c0-0x400-len(b)));b.extend(code)
    out.mkdir();(out/'engine.bin').write_bytes(b)
    paths=[Path(__file__),Path('tools/build_sweep_kernel.py'),parent/'manifest.json',parent/'engine.bin']
    meta.update(engine_sha256=sha(out/'engine.bin'),sources={str(p):sha(p) for p in paths},scope=__doc__)
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):p.add_argument('--'+k,type=Path,required=True)
    build(**vars(p.parse_args()))
