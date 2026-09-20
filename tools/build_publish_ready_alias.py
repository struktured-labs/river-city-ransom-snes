"""Pair a ready alias after a scalar row, with an independent existing beam gate."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

START = 0x5000


def assemble():
    with tempfile.TemporaryDirectory(prefix='rcr-ready-alias-') as temp:
        obj=Path(temp)/'helper.o';binary=Path(temp)/'helper.bin'
        subprocess.run(['.deps/cc65/bin/ca65','-o',str(obj),'snes/publish_ready_alias.asm'],check=True)
        subprocess.run(['.deps/cc65/bin/ld65','-C','snes/publish_ready_alias.cfg',
                        '-o',str(binary),str(obj)],check=True)
        return binary.read_bytes()


def build(parent,out):
    rom=parent/'native-cpu.sfc'
    if out.exists() or sha(rom)!='e269de592e045130e8e0478acd1728b51200d6144834b95bdf868f5a5f5ebc9b':
        raise ValueError('Exact3883 and fresh output required')
    image=bytearray(rom.read_bytes());helper=assemble()
    if (image[0x842f:0x843a]!=bytes.fromhex('8d0b42c220a51a38e51e85') or
            image[START:START+len(helper)]!=b'\xff'*len(helper)):
        raise ValueError('Changed scalar DMA site or occupied helper area')
    image[START:START+len(helper)]=helper
    image[0x842f:0x8432]=bytes((0x20,START&255,START>>8))
    checksum(image);out.mkdir(parents=True)
    for p in parent.iterdir():
        if p.is_file():shutil.copyfile(p,out/p.name)
    (out/'native-cpu.sfc').write_bytes(image)
    (out/'publish-ready-alias.bin').write_bytes(helper)
    paths=[Path(__file__),Path('snes/publish_ready_alias.asm'),Path('snes/publish_ready_alias.cfg'),
        Path('tools/build_inline_pitch_trial.py'),Path('.deps/cc65/bin/ca65'),
        Path('.deps/cc65/bin/ld65'),rom,parent/'manifest.json']
    meta=json.loads((parent/'manifest.json').read_text())
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_publish_ready_alias=dict(
        sources={str(p):sha(p) for p in paths},release_ready=False,scope=__doc__))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),bytes=len(helper),rom_sha256=meta['rom_sha256'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):p.add_argument('--'+k,type=Path,required=True)
    build(**vars(p.parse_args()))
