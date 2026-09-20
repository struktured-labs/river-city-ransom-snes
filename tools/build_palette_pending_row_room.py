"""Reserve earlier final publication while original palette-update bit3 is pending."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum


def assemble():
    with tempfile.TemporaryDirectory(prefix='rcr-palette-room-') as temp:
        obj=Path(temp)/'helper.o';binary=Path(temp)/'helper.bin'
        subprocess.run(['.deps/cc65/bin/ca65','-o',str(obj),'snes/palette_pending_row_room.asm'],check=True)
        subprocess.run(['.deps/cc65/bin/ld65','-C','snes/palette_pending_row_room.cfg','-o',str(binary),str(obj)],check=True)
        return binary.read_bytes()


def build(parent,out):
    rom=parent/'native-cpu.sfc'
    if out.exists() or sha(rom)!='86bace9a8818ba7b4a6530e350066495aad8f46cb7f1eaf40f0cc237f8804f1f':
        raise ValueError('Exact3780 and fresh output required')
    original=rom.read_bytes();helper=assemble()
    if (original[0x87fd:0x8807]!=bytes.fromhex('a51cc9fcb00238601860') or
            original[0x77e0:0x77e0+len(helper)]!=b'\xff'*len(helper)):
        raise ValueError('Changed guard or occupied helper')
    image=bytearray(original)
    image[0x87fd:0x8803]=bytes.fromhex('4ce077eaeaea')
    image[0x77e0:0x77e0+len(helper)]=helper
    checksum(image)
    changes=[i for i,(a,b) in enumerate(zip(original,image)) if a!=b]
    if any(not(0x87fd<=i<0x8803 or 0x77e0<=i<0x77e0+len(helper) or 0xffdc<=i<0xffe0) for i in changes):
        raise ValueError('Unrelated mutation')
    out.mkdir(parents=True)
    for p in parent.iterdir():
        if p.is_file():shutil.copy2(p,out/p.name)
    (out/'native-cpu.sfc').write_bytes(image);(out/'palette-row-room.bin').write_bytes(helper)
    paths=[Path(__file__),Path('snes/palette_pending_row_room.asm'),Path('snes/palette_pending_row_room.cfg'),
           Path('tools/build_inline_pitch_trial.py'),Path('.deps/cc65/bin/ca65'),Path('.deps/cc65/bin/ld65'),
           rom,parent/'manifest.json']
    meta=json.loads((parent/'manifest.json').read_text())
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_palette_pending_row_room=dict(
        sources={str(p):sha(p) for p in paths},changed_offsets=changes,helper=helper.hex(),
        release_ready=False,scope=__doc__+' Original flag is only read. No new dirty flag, '
        'skipped palette DMA, altered source data or relaxed transfer deadline.'))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'],helper_bytes=len(helper))))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):parser.add_argument('--'+k,type=Path,required=True)
    build(**vars(parser.parse_args()))
