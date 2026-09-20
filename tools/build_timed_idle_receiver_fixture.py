"""Preserve legacy envelope service as well as sweep service during staged waits."""
import argparse
import json
from pathlib import Path
from tools.build_timed_receiver_fixture import stage as timed
from tools.benchmark_report import sha


def stage(base):
    raw,labels=timed(base);result=bytearray(raw)
    # X is the receiver index. Both legacy and sweep/volume idle work can
    # clobber X/Y; preserve them while all active APU bytes remain old.
    helper=bytes.fromhex('4d6d3f53073f5534eece6f')
    result.extend(bytes(0x3670-0x400-len(result)));result.extend(helper)
    changed=[]
    for start,end in ((0x3540,labels['arm']),(labels['wait'],labels['tail']),(labels['hold'],labels['commit'])):
        old=bytes.fromhex('3f5534') if start==labels['hold'] else bytes.fromhex('3f7d32')
        hits=[i for i in range(start-0x400,end-0x400) if result.startswith(old,i)]
        if len(hits)!=1:raise ValueError('Changed staging service sites')
        at=hits[0];result[at:at+3]=bytes.fromhex('3f7036');changed.append(at+0x400)
    return bytes(result),dict(labels,service_idle=0x3670),changed


def build(parent,out):
    if out.exists():raise ValueError('Fresh output required')
    meta=json.loads((parent/'manifest.json').read_text());rom=parent/'native-cpu.sfc'
    if sha(rom)!=meta['rom_sha256']:raise ValueError('Changed parent')
    at=meta['sweep_driver_rom_offset'];base=rom.read_bytes()[at:at+meta['sweep_driver_layout']['engine_bytes']]
    result,labels,sites=stage(base);out.mkdir();(out/'engine.bin').write_bytes(result)
    paths=[Path(__file__),Path('tools/build_timed_receiver_fixture.py'),Path('tools/build_staged_receiver_fixture.py'),Path('tools/build_sweep_kernel.py'),rom,parent/'manifest.json']
    (out/'manifest.json').write_text(json.dumps(dict(engine_sha256=sha(out/'engine.bin'),labels=labels,service_sites=sites,
        layout=meta['sweep_driver_layout'],sources={str(p):sha(p) for p in paths},fixture_only=True,release_ready=False,scope=__doc__),indent=2)+'\n')
    print(json.dumps(dict(bytes=len(result),sites=sites)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):p.add_argument('--'+k,type=Path,required=True)
    build(**vars(p.parse_args()))
