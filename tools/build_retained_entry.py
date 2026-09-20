"""Complete an already-retained original job before assigning a newly arrived event ID."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_retained_producer_guard import symbols

HELPER, SIZE = 0x7400, 512


def patch(image,helper,entry,nmi):
    if len(image)!=0x200000 or len(helper)!=SIZE or not HELPER<=entry<HELPER+SIZE:
        raise ValueError('Wrong cartridge/helper extent')
    if image[nmi:nmi+7]!=bytes.fromhex('9c004248ad1042'):
        raise ValueError('Different native hardware acknowledgment')
    result=bytearray(image)
    # Only bank00's physical ROM is shared with its C0 alias; game mirrors
    # contain original PRG in this range and must not be patched as native code.
    result[nmi:nmi+7]=b'\x5c'+entry.to_bytes(2,'little')+b'\xc1\xea\xea\xea'
    allowed=set(range(nmi,nmi+7))|set(range(0xffdc,0xffe0))
    for bank in range(1,9):
        at=bank*65536+HELPER
        if image[at:at+SIZE]!=b'\xff'*SIZE:raise ValueError('Occupied retained-entry helper')
        result[at:at+SIZE]=helper;allowed.update(range(at,at+SIZE))
    checksum(result)
    if any(i not in allowed for i,(a,b) in enumerate(zip(image,result)) if a!=b):
        raise ValueError('Unrelated cartridge edit')
    return bytes(result)


def build(parent,out):
    if out.exists():raise ValueError('Fresh output required')
    meta=json.loads((parent/'manifest.json').read_text());rom=parent/'native-cpu.sfc'
    if sha(rom)!=meta['rom_sha256'] or not meta['experimental_queued_vblank'].get('read_poll'):
        raise ValueError('Need authenticated cheaper-queue parent')
    boot=symbols(parent/'native_boot.lbl')
    defs=dict(NATIVE_GAME=boot['@game_nmi'],NATIVE_AFTER_ACK=boot['nmi']+7)
    out.mkdir(parents=True)
    for p in parent.iterdir():
        if p.is_file():shutil.copy2(p,out/p.name)
    subprocess.run(['.deps/cc65/bin/ca65',*[v for k,n in defs.items() for v in ('-D',f'{k}={n}')],
        '-o',str(out/'retained-entry.o'),'snes/retained_entry.asm'],check=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/retained_entry.cfg','-Ln',str(out/'retained-entry.lbl'),
        '-o',str(out/'retained-entry.bin'),str(out/'retained-entry.o')],check=True)
    entries=symbols(out/'retained-entry.lbl')
    (out/'native-cpu.sfc').write_bytes(patch(rom.read_bytes(),(out/'retained-entry.bin').read_bytes(),
        entries['retained_hardware_entry'],boot['nmi']))
    paths=[Path(__file__),Path('snes/retained_entry.asm'),Path('snes/retained_entry.cfg'),
        Path('tools/build_inline_pitch_trial.py'),Path('tools/build_retained_producer_guard.py'),
        Path('.deps/cc65/bin/ca65'),Path('.deps/cc65/bin/ld65'),rom,parent/'manifest.json',
        parent/'native_boot.lbl',out/'retained-entry.bin',out/'retained-entry.lbl']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_retained_entry=dict(
        parent=str(parent),helper=HELPER,size=SIZE,entries=entries,definitions=defs,
        sources={str(p):sha(p) for p in paths},release_ready=False,scope=__doc__))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'])))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):parser.add_argument('--'+k,type=Path,required=True)
    build(**vars(parser.parse_args()))
