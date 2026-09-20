"""Keep paired SPC polling local; preserve timer consumption and receive-store PCs."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

ORIGIN=0x3530
CODE=bytes.fromhex('e4fdf0033f84323ef4d0f55fe132')


def patch(engine):
    if len(engine)!=0x3140:raise ValueError('Wrong fixed engine size')
    data=bytearray(engine)
    if data[0x2eda:0x2ee5]!=bytes.fromhex('3ef4f0035fa02fe4f5d440'):
        raise ValueError('Changed receiver dispatch/store')
    if data[0x2ba0:0x2baa]!=bytes.fromhex('e4fdf0033f84325fda32'):
        raise ValueError('Changed timer helper')
    if data[0x2e84:0x2e88]!=bytes.fromhex('c49f4d6d'):
        raise ValueError('Changed pending timer entry')
    if data[ORIGIN-0x400:ORIGIN-0x400+len(CODE)]!=bytes(len(CODE)):
        raise ValueError('Occupied engine-tail padding')
    data[ORIGIN-0x400:ORIGIN-0x400+len(CODE)]=CODE
    data[0x2edf:0x2ee1]=ORIGIN.to_bytes(2,'little')
    return bytes(data)


def build(parent,out):
    rom=parent/'native-cpu.sfc'
    if out.exists() or sha(rom)!='67fa19ee60b76af7c8e7ec581075eabb97efb19e7ce933e2cc34db66882cbda2':
        raise ValueError('Exact3890 and fresh output required')
    meta=json.loads((parent/'manifest.json').read_text());image=bytearray(rom.read_bytes())
    at=meta['sweep_driver_rom_offset'];size=meta['sweep_driver_layout']['engine_bytes']
    old=bytes(image[at:at+size])
    if hashlib.sha256(old).hexdigest()!=meta['spc_sha256']:raise ValueError('Changed engine')
    engine=patch(old);image[at:at+size]=engine;checksum(image);out.mkdir()
    for p in parent.iterdir():
        if p.is_file():shutil.copyfile(p,out/p.name)
    (out/'native-cpu.sfc').write_bytes(image)
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),spc_sha256=hashlib.sha256(engine).hexdigest(),
        experimental_receiver_local_poll=dict(origin=ORIGIN,code=CODE.hex(),release_ready=False,
        sources={str(p):sha(p) for p in (Path(__file__),Path('tools/build_inline_pitch_trial.py'),
            Path('tools/build_interleaved_restart_volume.py'),rom,parent/'manifest.json')},
        scope=__doc__+' Fixed upload length. Tail bytes were zero padding after the interleaved flush.'))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(rom_sha256=meta['rom_sha256'],spc_sha256=meta['spc_sha256'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):p.add_argument('--'+k,type=Path,required=True)
    build(**vars(p.parse_args()))
