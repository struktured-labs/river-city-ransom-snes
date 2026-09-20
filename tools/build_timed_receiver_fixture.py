"""Fixture-only automatic staged commit using the existing consumed Timer0 ticks."""
import argparse
import hashlib
import json
from pathlib import Path
from tools.build_sweep_kernel import Program
from tools.build_staged_receiver_fixture import ENGINE_SHA,BUFFER
from tools.benchmark_report import sha


def stage(engine):
    if hashlib.sha256(engine).hexdigest()!=ENGINE_SHA:raise ValueError('Exact3955 engine required')
    p=Program(0x3540)
    p.label('receiver');p.put(0x3e,0xf4);p.when(0xd0,'wait')
    p.put(0xc8,0);p.when(0xd0,'data')
    p.put(0x3f,0x7d,0x32) # Account for old timer delta before arming.
    p.label('arm');p.put(0xe4,0xf7,0x68,33);p.when(0x90,'header_ok')
    p.put(0xe8,32) # Invalid large header cannot stall a producer indefinitely.
    p.label('header_ok');p.put(0xc5,0x18,0x36)
    p.label('data');p.put(0xe4,0xf5,0xd5,0,0x36,0x3d,0xc8,23);p.when(0xf0,'tail')
    p.put(0xe4,0xf6,0xd5,0,0x36,0x1d,0xd8,0xf4,0x3d,0x3d);p.jump('receiver')
    p.label('wait');p.put(0x3f,0x7d,0x32);p.jump('receiver')
    p.label('tail');p.put(0x1d,0xd8,0xf4,0x3d,0xe8,1,0xc5,0x17,0x36)
    p.label('hold');p.put(0xe5,0x18,0x36);p.when(0xf0,'commit')
    p.put(0x3f,0x55,0x34);p.jump('hold')
    p.label('commit');p.put(0xcd,0)
    p.label('copy');p.put(0xf5,0,0x36,0xd4,0x40,0x3d,0xc8,23);p.when(0xd0,'copy')
    p.put(0xe8,0,0xc5,0x17,0x36,0x3f,0xca,0x32,0x5f,0x1f,0x30)
    code,labels=p.result()
    if 0x3540+len(code)>BUFFER:raise ValueError('Receiver overlaps buffer')
    q=Program(0x3640)
    q.label('advance_wrapper')
    q.put(0x2d,0xc5,0x19,0x36,0xe5,0x18,0x36,0x80,0xa5,0x19,0x36)
    q.when(0xb0,'store');q.put(0xe8,0)
    q.label('store');q.put(0xc5,0x18,0x36,0xae,0x5f,0x32,0x32)
    wrapper,extra=q.result();labels.update(extra)
    result=bytearray(engine+code);result.extend(bytes(0x3640-0x400-len(result)));result.extend(wrapper)
    if result[0x87:0x8a]!=bytes.fromhex('5fda32'):raise ValueError('Changed dispatch')
    result[0x87:0x8a]=bytes.fromhex('5f4035')
    for pc in (0x3279,0x3296):
        at=pc-0x400
        if result[at:at+3]!=bytes.fromhex('3f3232'):raise ValueError('Changed timer delta call')
        result[at:at+3]=bytes.fromhex('3f4036')
    return bytes(result),labels


def build(parent,out):
    if out.exists():raise ValueError('Fresh fixture output required')
    meta=json.loads((parent/'manifest.json').read_text());rom=parent/'native-cpu.sfc'
    if sha(rom)!=meta['rom_sha256']:raise ValueError('Changed parent')
    at=meta['sweep_driver_rom_offset'];image=rom.read_bytes()[at:at+meta['sweep_driver_layout']['engine_bytes']]
    result,labels=stage(image);out.mkdir();(out/'engine.bin').write_bytes(result)
    paths=[Path(__file__),Path('tools/build_sweep_kernel.py'),Path('tools/build_staged_receiver_fixture.py'),rom,parent/'manifest.json']
    (out/'manifest.json').write_text(json.dumps(dict(engine_sha256=sha(out/'engine.bin'),labels=labels,
        layout=meta['sweep_driver_layout'],sources={str(p):sha(p) for p in paths},fixture_only=True,
        deadline_unit_clocks=512,maximum_header_ticks=32,release_ready=False,scope=__doc__),indent=2)+'\n')
    print(json.dumps(dict(bytes=len(result),labels=labels)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):p.add_argument('--'+k,type=Path,required=True)
    build(**vars(p.parse_args()))
