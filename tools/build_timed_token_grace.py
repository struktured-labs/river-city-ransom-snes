"""Give an in-flight CPU token a bounded arrival window before idle sound work."""
import argparse
import json
from pathlib import Path
from tools.build_sweep_kernel import Program
from tools.review_command_priority import bound
from tools.benchmark_report import sha


def build(parent,out,window=16):
    if out.exists():raise ValueError('Fresh output required')
    if not 1<=window<=255:raise ValueError('Poll window must fit in Y')
    m=bound(parent/'manifest.json');b=bytearray((parent/'engine.bin').read_bytes());at=m['labels']['wait']-0x400
    if sha(parent/'engine.bin')!=m['engine_sha256'] or b[at:at+3]!=bytes.fromhex('3f0037'):
        raise ValueError('Changed wait path')
    p=Program(0x3720);p.put(0x6d,0x8d,window)
    p.label('poll');p.put(0x3e,0xf4);p.when(0xf0,'ready');p.put(0xdc);p.when(0xd0,'poll')
    p.put(0xee,0x5f,0x00,0x37)
    p.label('ready');p.put(0xee,0x6f)
    code,_=p.result()
    if len(b)>0x3720-0x400:raise ValueError('Occupied helper')
    b[at:at+3]=bytes.fromhex('3f2037');b.extend(bytes(0x3720-0x400-len(b)));b.extend(code)
    out.mkdir();(out/'engine.bin').write_bytes(b)
    paths=[Path(__file__),Path('tools/build_sweep_kernel.py'),parent/'manifest.json',parent/'engine.bin']
    m.update(engine_sha256=sha(out/'engine.bin'),poll_window=window,
        sources={str(p):sha(p) for p in paths},scope=__doc__)
    (out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--window',type=int,default=16)
    build(**vars(p.parse_args()))
