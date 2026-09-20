"""Delay an already eligible early boundary tick until the unchanged phase80."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum


def assemble():
    with tempfile.TemporaryDirectory(prefix='rcr-audio-wait80-') as d:
        obj=Path(d)/'helper.o';raw=Path(d)/'helper.bin'
        subprocess.run(['.deps/cc65/bin/ca65','-o',str(obj),'snes/audio_boundary_wait80.asm'],check=True)
        subprocess.run(['.deps/cc65/bin/ld65','-C','snes/audio_boundary_wait80.cfg','-o',str(raw),str(obj)],check=True)
        return raw.read_bytes()


def patch(data,helper):
    image=bytearray(data)
    for bank in range(1,9):
        base=bank*65536
        if image[base+0x7bb4:base+0x7bc0]!=bytes.fromhex('e0209007e0f0b003208578ab'):
            raise ValueError('Changed boundary admission or service call')
        if image[base+0x7f40:base+0x7f40+len(helper)]!=b'\xff'*len(helper):
            raise ValueError('Occupied helper space')
        image[base+0x7f40:base+0x7f40+len(helper)]=helper
        image[base+0x7bbc:base+0x7bbf]=bytes.fromhex('20407f')
    checksum(image)
    return image


def build(parent,out):
    rom=parent/'native-cpu.sfc'
    if out.exists() or sha(rom)!='67fa19ee60b76af7c8e7ec581075eabb97efb19e7ce933e2cc34db66882cbda2':
        raise ValueError('Exact3890 and fresh output required')
    helper=assemble();image=patch(rom.read_bytes(),helper);out.mkdir()
    for p in parent.iterdir():
        if p.is_file():shutil.copyfile(p,out/p.name)
    (out/'native-cpu.sfc').write_bytes(image)
    paths=[Path(__file__),Path('snes/audio_boundary_wait80.asm'),Path('snes/audio_boundary_wait80.cfg'),
        Path('tools/build_inline_pitch_trial.py'),Path('.deps/cc65/bin/ca65'),Path('.deps/cc65/bin/ld65'),rom,parent/'manifest.json']
    meta=json.loads((parent/'manifest.json').read_text())
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_audio_boundary_wait80=dict(
        sources={str(p):sha(p) for p in paths},helper_bytes=len(helper),release_ready=False))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(rom_sha256=meta['rom_sha256'],helper_bytes=len(helper))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):p.add_argument('--'+k,type=Path,required=True)
    build(**vars(p.parse_args()))
