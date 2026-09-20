"""Requalify static OAM-tail elision on exact receiver3934; keep hidden uploads full."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

START=0x5100
OLD=bytes.fromhex('9c02219c03219c0043a9048d0143a200508e0243a97e8d0443a220028e0543a9018d0b42a9808d152160')
PARENT='cfa07c033f0cf7211f5f5b2c28d214f562c3f384518b6ad24aae5d1f43281912'


def assemble():
    with tempfile.TemporaryDirectory(prefix='rcr-early-half-') as temp:
        obj=Path(temp)/'helper.o';binary=Path(temp)/'helper.bin'
        subprocess.run(['.deps/cc65/bin/ca65','-I','snes','-o',str(obj),'snes/early_oam_live_half.asm'],check=True)
        subprocess.run(['.deps/cc65/bin/ld65','-C','snes/early_oam_live_half.cfg','-o',str(binary),str(obj)],check=True)
        return binary.read_bytes()


def patch(original,helper):
    if original[0x7300:0x7300+len(OLD)]!=OLD or original[START:START+len(helper)]!=b'\xff'*len(helper):
        raise ValueError('Changed early OAM helper or occupied extension')
    image=bytearray(original)
    image[START:START+len(helper)]=helper
    image[0x7300:0x7303]=bytes.fromhex('4c0051')
    checksum(image)
    return bytes(image)


def build(parent,out):
    rom=parent/'native-cpu.sfc'
    if out.exists() or sha(rom)!=PARENT:
        raise ValueError('Exact3934 and fresh output required')
    helper=assemble();original=rom.read_bytes();image=patch(original,helper)
    changed=[i for i,(a,b) in enumerate(zip(original,image)) if a!=b]
    if any(not(START<=i<START+len(helper) or 0x7300<=i<0x7303 or 0xffdc<=i<0xffe0) for i in changed):
        raise ValueError('Unrelated mutation')
    out.mkdir()
    for p in parent.iterdir():
        if p.is_file():shutil.copyfile(p,out/p.name)
    (out/'native-cpu.sfc').write_bytes(image);(out/'early-oam-live-half.bin').write_bytes(helper)
    paths=[Path(__file__),Path('snes/early_oam_live_half.asm'),Path('snes/early_oam_live_half.cfg'),
           Path('snes/oam_live_half.inc'),Path('tools/build_inline_pitch_trial.py'),
           Path('.deps/cc65/bin/ca65'),Path('.deps/cc65/bin/ld65'),rom,parent/'manifest.json']
    meta=json.loads((parent/'manifest.json').read_text())
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_early_oam_live_half=dict(
        sources={str(p):sha(p) for p in paths},changes=changed,release_ready=False,
        scope=__doc__,latch='boot-cleared1BF0',visible_bytes=256,initial_or_hidden_bytes=544))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(bytes=len(helper),rom_sha256=meta['rom_sha256'],out=str(out))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):p.add_argument('--'+k,type=Path,required=True)
    build(**vars(p.parse_args()))
