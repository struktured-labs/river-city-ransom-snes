"""Fixture-only staged SPC receiver; explicit D8 commit, no cartridge deployment."""
import argparse
import hashlib
import json
from pathlib import Path
from tools.build_sweep_kernel import Program
from tools.benchmark_report import sha

ENGINE_SHA='2759ff50446456621e9131954f1302ea2e073d96abe1d469a0b3e92cb3e09e32'
BUFFER=0x3600


def stage(engine):
    if hashlib.sha256(engine).hexdigest()!=ENGINE_SHA:raise ValueError('Exact3955 SPC required')
    p=Program(0x3540)
    p.label('receiver')
    p.put(0x3e,0xf4);p.when(0xd0,'wait')
    p.put(0xe4,0xf5,0xd5,0,0x36,0x3d,0xc8,23);p.when(0xf0,'tail')
    p.put(0xe4,0xf6,0xd5,0,0x36,0x1d,0xd8,0xf4,0x3d,0x3d)
    p.jump('receiver')
    p.label('wait');p.put(0x3f,0x7d,0x32);p.jump('receiver')
    p.label('tail');p.put(0x1d,0xd8,0xf4,0x3d,0xe8,1,0xc5,0x17,0x36)
    p.label('hold')
    p.put(0xe4,0xf4,0x68,0xd8);p.when(0xf0,'commit')
    p.put(0x3f,0x55,0x34);p.jump('hold')
    p.label('commit');p.put(0xcd,0)
    p.label('copy');p.put(0xf5,0,0x36,0xd4,0x40,0x3d,0xc8,23);p.when(0xd0,'copy')
    p.put(0xe8,0,0xc5,0x17,0x36,0x3f,0xca,0x32,0x5f,0x1f,0x30)
    code,labels=p.result()
    if 0x3540+len(code)>BUFFER:raise ValueError('Code overlaps staging buffer')
    result=bytearray(engine+code)
    result.extend(bytes(BUFFER+24-0x400-len(result)))
    if result[0x87:0x8a]!=bytes.fromhex('5fda32'):raise ValueError('Changed receiver dispatch')
    result[0x87:0x8a]=bytes.fromhex('5f4035')
    return bytes(result),labels


def build(parent,out):
    if out.exists():raise ValueError('Fresh fixture output required')
    meta=json.loads((parent/'manifest.json').read_text());rom=parent/'native-cpu.sfc'
    if sha(rom)!=meta['rom_sha256']:raise ValueError('Changed cartridge')
    at=meta['sweep_driver_rom_offset'];engine=rom.read_bytes()[at:at+meta['sweep_driver_layout']['engine_bytes']]
    result,labels=stage(engine);out.mkdir()
    (out/'engine.bin').write_bytes(result)
    paths=[Path(__file__),Path('tools/build_sweep_kernel.py'),rom,parent/'manifest.json']
    report=dict(engine_sha256=sha(out/'engine.bin'),labels=labels,buffer=BUFFER,layout=meta['sweep_driver_layout'],
        sources={str(p):sha(p) for p in paths},fixture_only=True,release_ready=False,scope=__doc__)
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(bytes=len(result),labels=labels)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):p.add_argument('--'+k,type=Path,required=True)
    build(**vars(p.parse_args()))
