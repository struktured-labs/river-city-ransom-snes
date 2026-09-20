"""Run full old-state envelope service on timer ticks, not every empty token poll."""
import argparse
import json
from pathlib import Path
from tools.build_sweep_kernel import Program
from tools.review_command_priority import bound
from tools.benchmark_report import sha


def build(parent,out):
    if out.exists():raise ValueError('Fresh output required')
    m=bound(parent/'manifest.json');b=bytearray((parent/'engine.bin').read_bytes())
    if sha(parent/'engine.bin')!=m['engine_sha256']:raise ValueError('Changed engine')
    at=m['labels']['wait']-0x400
    if b[at:at+3]!=bytes.fromhex('3f7036'):raise ValueError('Changed wait helper')
    p=Program(0x3700);p.put(0xe4,0xfd);p.when(0xf0,'done')
    p.put(0x3f,0x84,0x32,0x3f,0x70,0x36)
    p.label('done');p.put(0x6f)
    code,_=p.result()
    if len(b)>0x3700-0x400:raise ValueError('Occupied helper')
    b[at:at+3]=bytes.fromhex('3f0037');b.extend(bytes(0x3700-0x400-len(b)));b.extend(code)
    out.mkdir();(out/'engine.bin').write_bytes(b)
    paths=[Path(__file__),Path('tools/build_sweep_kernel.py'),parent/'manifest.json',parent/'engine.bin']
    m.update(engine_sha256=sha(out/'engine.bin'),sources={str(p):sha(p) for p in paths},scope=__doc__)
    (out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):p.add_argument('--'+k,type=Path,required=True)
    build(**vars(p.parse_args()))
