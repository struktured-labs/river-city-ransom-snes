"""Accept pending D7 before optional idle publication; keep receiver/ready timer work."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

ORIGIN=0x3523
CODE=bytes.fromhex('e4f468d7f0035f55346f')

def patch(engine):
    if hashlib.sha256(engine).hexdigest()!='2759ff50446456621e9131954f1302ea2e073d96abe1d469a0b3e92cb3e09e32':
        raise ValueError('Exact3955 engine required')
    if engine[0x77:0x7a]!=bytes.fromhex('3f5534') or engine[ORIGIN-0x400:ORIGIN-0x400+len(CODE)]!=bytes(len(CODE)):
        raise ValueError('Changed entry or occupied padding')
    b=bytearray(engine)
    b[0x77:0x7a]=bytes.fromhex('3f2335')
    b[ORIGIN-0x400:ORIGIN-0x400+len(CODE)]=CODE
    return bytes(b)

def build(parent,out):
    rom=parent/'native-cpu.sfc'
    if out.exists() or sha(rom)!='f6f69215716ecc077c9082da0a20db1eaaa064daab81b0992a54cade834d1e16':
        raise ValueError('Exact3955 and fresh output required')
    meta=json.loads((parent/'manifest.json').read_text()); old=rom.read_bytes(); b=bytearray(old)
    at=meta['sweep_driver_rom_offset']; size=meta['sweep_driver_layout']['engine_bytes']
    engine=patch(bytes(b[at:at+size]));b[at:at+size]=engine;checksum(b)
    allowed=set(range(at+0x77,at+0x7a))|set(range(at+ORIGIN-0x400,at+ORIGIN-0x400+len(CODE)))|set(range(0xffdc,0xffe0))
    if any(i not in allowed for i,(x,y) in enumerate(zip(old,b)) if x!=y):raise ValueError('Unrelated mutation')
    out.mkdir()
    for p in parent.iterdir():
        if p.is_file():shutil.copyfile(p,out/p.name)
    (out/'native-cpu.sfc').write_bytes(b)
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),spc_sha256=hashlib.sha256(engine).hexdigest(),
        experimental_command_priority=dict(origin=ORIGIN,code=CODE.hex(),release_ready=False,
            sources={str(p):sha(p) for p in (Path(__file__),Path('tools/build_inline_pitch_trial.py'),rom,parent/'manifest.json')},scope=__doc__))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(rom_sha256=meta['rom_sha256'],spc_sha256=meta['spc_sha256'])))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):p.add_argument('--'+k,type=Path,required=True)
    build(**vars(p.parse_args()))
