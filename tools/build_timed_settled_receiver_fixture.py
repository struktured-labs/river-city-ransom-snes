"""Arm timed staging only after accounting all pre-arm Timer0 deltas."""
import argparse
import json
from pathlib import Path
from tools.build_timed_idle_receiver_fixture import stage as idle
from tools.build_sweep_kernel import Program
from tools.benchmark_report import sha


def stage(base):
    raw,labels,sites=idle(base);result=bytearray(raw)
    p=Program(0x3690)
    p.put(0x3f,0x70,0x36)
    p.label('arm');p.put(0xe4,0xfd);p.when(0xf0,'settled')
    # Reuse the receiver's active-control-safe delta consumer. No timer
    # resets or discarded ticks, even if a half-frame service crosses a tick.
    p.put(0x3f,0x84,0x32);p.jump('arm')
    p.label('settled');p.put(0xe4,0xf7,0x68,33);p.when(0x90,'header_ok')
    p.put(0xe8,32);p.label('header_ok');p.put(0xc5,0x18,0x36,0x5f,0x5f,0x35)
    code,extra=p.result()
    at=0x354e-0x400;end=0x355f-0x400
    if result[at:at+3]!=bytes.fromhex('3f7036'):raise ValueError('Changed arm service')
    result[at:end]=bytes.fromhex('5f9036')+bytes(end-at-3)
    result.extend(bytes(0x3690-0x400-len(result)));result.extend(code)
    return bytes(result),dict(labels,**extra)


def build(parent,out):
    if out.exists():raise ValueError('Fresh output required')
    m=json.loads((parent/'manifest.json').read_text());rom=parent/'native-cpu.sfc'
    if sha(rom)!=m['rom_sha256']:raise ValueError('Changed parent')
    at=m['sweep_driver_rom_offset'];base=rom.read_bytes()[at:at+m['sweep_driver_layout']['engine_bytes']]
    image,labels=stage(base);out.mkdir();(out/'engine.bin').write_bytes(image)
    paths=[Path(__file__),Path('tools/build_timed_idle_receiver_fixture.py'),Path('tools/build_timed_receiver_fixture.py'),
        Path('tools/build_staged_receiver_fixture.py'),Path('tools/build_sweep_kernel.py'),rom,parent/'manifest.json']
    (out/'manifest.json').write_text(json.dumps(dict(engine_sha256=sha(out/'engine.bin'),labels=labels,
        layout=m['sweep_driver_layout'],sources={str(p):sha(p) for p in paths},fixture_only=True,release_ready=False,
        scope=__doc__),indent=2)+'\n')
    print(json.dumps(dict(bytes=len(image),labels=labels)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):p.add_argument('--'+k,type=Path,required=True)
    build(**vars(p.parse_args()))
