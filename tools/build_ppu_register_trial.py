"""Fast common PPU-register writes, preserving the legacy dispatcher ABI and fallback."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_retained_producer_guard import symbols

HELPER = 0x7000
SIZE = 256
PREFIX = bytes.fromhex('0848da5a0b9c0042')


def patch(image,helper,entry):
    if len(image) != 0x200000 or len(helper) != SIZE or not 0x2000 < entry < 0x4000:
        raise ValueError('Wrong cartridge/helper extent')
    changed = bytearray(image)
    allowed = set(range(0xffdc,0xffe0))
    for bank in range(1,9):
        base = bank*65536
        if (image[base+entry:base+entry+len(PREFIX)] != PREFIX or
                image[base+HELPER:base+HELPER+SIZE] != b'\xff'*SIZE):
            raise ValueError('Changed dispatcher or occupied helper')
        changed[base+entry:base+entry+3] = b'\x4c'+HELPER.to_bytes(2,'little')
        changed[base+HELPER:base+HELPER+SIZE] = helper
        allowed.update(range(base+entry,base+entry+3))
        allowed.update(range(base+HELPER,base+HELPER+SIZE))
    checksum(changed)
    if any(i not in allowed for i,(a,b) in enumerate(zip(image,changed)) if a != b):
        raise ValueError('Unrelated cartridge edit')
    return bytes(changed)


def build(parent,out):
    if out.exists():
        raise ValueError('Fresh output required')
    meta = json.loads((parent/'manifest.json').read_text())
    rom = parent/'native-cpu.sfc'
    if sha(rom) != meta['rom_sha256'] or not meta['experimental_chr_dirty_gate']:
        raise ValueError('Need authenticated CHR-dirty-gated parent')
    labels = symbols(parent/'native_runtime.lbl')
    entry = labels['dispatch_write']
    # Pin the precise legacy PPU semantics we specialize, not merely the flag.
    expected = bytes.fromhex('484d201c2918f005a9018dbb1c688d201c')
    image = rom.read_bytes()
    body = image[65536+labels['ppu_write']:65536+labels['mark_ppu_dirty']]
    if body.count(expected) != 1:
        raise ValueError('Different legacy PPUCTRL behavior')
    for bank in range(1,9):
        if image[bank*65536+labels['ppu_write']:bank*65536+labels['mark_ppu_dirty']] != body:
            raise ValueError('Different mirrored PPU behavior')
    out.mkdir(parents=True)
    for p in parent.iterdir():
        if p.is_file():
            shutil.copy2(p,out/p.name)
    subprocess.run(['.deps/cc65/bin/ca65','-D',f'OLD_BODY={entry+3}',
        '-o',str(out/'ppu-register.o'),'snes/ppu_register_fast.asm'],check=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/ppu_register_fast.cfg',
        '-Ln',str(out/'ppu-register.lbl'),'-o',str(out/'ppu-register.bin'),str(out/'ppu-register.o')],check=True)
    (out/'native-cpu.sfc').write_bytes(patch(rom.read_bytes(),(out/'ppu-register.bin').read_bytes(),entry))
    paths = [Path(__file__),Path('snes/ppu_register_fast.asm'),Path('snes/ppu_register_fast.cfg'),
             Path('tools/build_inline_pitch_trial.py'),Path('tools/build_retained_producer_guard.py'),
             Path('.deps/cc65/bin/ca65'),Path('.deps/cc65/bin/ld65'),rom,
             parent/'manifest.json',parent/'native_runtime.lbl',out/'ppu-register.bin',out/'ppu-register.lbl']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_ppu_register_fast=dict(
        parent=str(parent),entry=entry,helper=HELPER,size=SIZE,sources={str(p):sha(p) for p in paths},
        release_ready=False,scope=__doc__))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):
        p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
