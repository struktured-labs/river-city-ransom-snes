"""Remove duplicate pre-arm idle pass; main dispatch and timed waits retain service."""
import argparse
import json
from pathlib import Path
from tools.review_command_priority import bound
from tools.benchmark_report import sha


def build(parent,out):
    if out.exists():raise ValueError('Fresh output required')
    m=bound(parent/'manifest.json');b=bytearray((parent/'engine.bin').read_bytes());at=0x3690-0x400
    if sha(parent/'engine.bin')!=m['engine_sha256'] or b[at:at+3]!=bytes.fromhex('3f7036'):
        raise ValueError('Changed pre-arm service')
    b[at:at+3]=bytes(3);out.mkdir();(out/'engine.bin').write_bytes(b)
    paths=[Path(__file__),parent/'manifest.json',parent/'engine.bin']
    m.update(engine_sha256=sha(out/'engine.bin'),sources={str(p):sha(p) for p in paths},scope=__doc__)
    (out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):p.add_argument('--'+k,type=Path,required=True)
    build(**vars(p.parse_args()))
