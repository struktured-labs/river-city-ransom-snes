"""Check an already pending data token before consuming the receiver timer."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

ORIGIN=0x3530
OLD=bytes.fromhex('e4fdf0033f84323ef4d0f55fe1320000')
CODE=bytes.fromhex('3ef4f009e4fdf0033f84322ff35fe132')

def patch(engine):
    if hashlib.sha256(engine).hexdigest()!='513ca1fd1422618e3350b507aa71cca97199f75dacd1257563e2bd0b1c194d38':
        raise ValueError('Exact3996 engine required')
    at=ORIGIN-0x400
    if engine[at:at+16]!=OLD:raise ValueError('Changed receiver or padding')
    b=bytearray(engine);b[at:at+16]=CODE
    return bytes(b)

def build(parent,out):
    rom=parent/'native-cpu.sfc'
    if out.exists() or sha(rom)!='caf6dad312f4bd1d8009dfee849d26657d128472a35d52002831eb30c0577ae3':
        raise ValueError('Exact3996 and fresh output required')
    meta=json.loads((parent/'manifest.json').read_text());old=rom.read_bytes();b=bytearray(old)
    at=meta['sweep_driver_rom_offset'];size=meta['sweep_driver_layout']['engine_bytes']
    engine=patch(bytes(b[at:at+size]));b[at:at+size]=engine;checksum(b)
    allowed=set(range(at+ORIGIN-0x400,at+ORIGIN-0x400+16))|set(range(0xffdc,0xffe0))
    if len(b)!=len(old) or any(i not in allowed for i,(x,y) in enumerate(zip(old,b)) if x!=y):raise ValueError('Unrelated mutation')
    out.mkdir()
    for p in parent.iterdir():
        if p.is_file():shutil.copyfile(p,out/p.name)
    (out/'native-cpu.sfc').write_bytes(b)
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),spc_sha256=hashlib.sha256(engine).hexdigest(),
        experimental_receiver_token_priority=dict(origin=ORIGIN,code=CODE.hex(),release_ready=False,
            sources={str(p):sha(p) for p in (Path(__file__),Path('tools/build_inline_pitch_trial.py'),rom,parent/'manifest.json')},scope=__doc__))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(rom_sha256=meta['rom_sha256'],spc_sha256=meta['spc_sha256'])))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):p.add_argument('--'+k,type=Path,required=True)
    build(**vars(p.parse_args()))
