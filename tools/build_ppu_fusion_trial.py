"""Fuse known PPU write-stub ABI with private specialized callees; epilogues stay exact."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_native import stub as canonical_stub
from tools.build_ppu_register_trial import HELPER,SIZE,PREFIX
from tools.build_retained_producer_guard import symbols

NAMES = {0:'fused_control',3:'fused_oam_address',5:'fused_scroll',6:'fused_address'}


def targets(image,meta,entry):
    stubs = sorted(set(r['stub'] for r in meta['patches']))
    ends = dict(zip(stubs,stubs[1:]+[0x6000+meta['stub_bytes']]))
    chosen = {}
    for row in meta['patches']:
        address,opcode = row.get('operand',-1),row.get('opcode')
        if opcode not in (0x8d,0x8e,0x8c) or address>>8!=0x20 or address&7 not in NAMES:
            continue
        start = row['stub']
        if not 0x6000<=start<ends[start]<=HELPER:
            raise ValueError('Invalid stub extent')
        body = image[65536+start:65536+ends[start]]
        resume = int.from_bytes(body[-2:],'little') if body[-3]==0x4c else None
        expected = canonical_stub(opcode,address,entry,resume=resume)
        if body!=expected:
            raise ValueError('Stub is not the exact saved-A/P, immediate-PLA/PLP ABI')
        record = dict(start=start,end=ends[start],address=address,opcode=opcode,resume=resume)
        if start in chosen and chosen[start]!=record:
            raise ValueError('Aliased stub metadata disagrees')
        chosen[start] = record
    if not chosen:
        raise ValueError('No target stubs')
    return [chosen[k] for k in sorted(chosen)]


def patch(image,helper,entries,entry,meta):
    if len(image)!=0x200000 or len(helper)!=SIZE:
        raise ValueError('Wrong image/helper extent')
    if any(not HELPER<=entries[name]<HELPER+SIZE for name in NAMES.values()):
        raise ValueError('Wrong helper entry')
    records = targets(image,meta,entry)
    changed = bytearray(image)
    allowed = set(range(0xffdc,0xffe0))
    sites = []
    needle = b'\x22'+entry.to_bytes(2,'little')+b'\xc1\x68\x28'
    for bank in range(1,9):
        base = bank*65536
        if (image[base+entry:base+entry+len(PREFIX)]!=PREFIX or
                image[base+HELPER:base+HELPER+SIZE]!=b'\xff'*SIZE):
            raise ValueError('Changed dispatcher or occupied helper')
        for row in records:
            first,last = row['start'],row['end']
            body = image[base+first:base+last]
            if body!=image[65536+first:65536+last] or body.count(needle)!=1:
                raise ValueError('Different mirrored caller/restore ABI')
            at = base+first+body.index(needle)+1
            address = entries[NAMES[row['address']&7]]
            changed[at:at+2] = address.to_bytes(2,'little')
            sites.append(dict(site=at,entry=address,stub=first))
            allowed.update((at,at+1))
        changed[base+HELPER:base+HELPER+SIZE] = helper
        allowed.update(range(base+HELPER,base+HELPER+SIZE))
    checksum(changed)
    if any(i not in allowed for i,(a,b) in enumerate(zip(image,changed)) if a!=b):
        raise ValueError('Unrelated edit')
    return bytes(changed),records,sites


def build(parent,out):
    if out.exists():
        raise ValueError('Fresh output required')
    meta = json.loads((parent/'manifest.json').read_text())
    rom = parent/'native-cpu.sfc'
    if sha(rom)!=meta['rom_sha256'] or not meta['experimental_chr_dirty_gate'] or meta['experimental_raster']:
        raise ValueError('Wrong parent policy/source')
    labels = symbols(parent/'native_runtime.lbl')
    image = rom.read_bytes()
    ppu = image[65536+labels['ppu_write']:65536+labels['mark_ppu_dirty']]
    if ppu.count(bytes.fromhex('484d201c2918f005a9018dbb1c688d201c'))!=1:
        raise ValueError('Different CHR dirty behavior')
    for bank in range(1,9):
        if image[bank*65536+labels['ppu_write']:bank*65536+labels['mark_ppu_dirty']]!=ppu:
            raise ValueError('Different mirrored PPU behavior')
    out.mkdir(parents=True)
    for p in parent.iterdir():
        if p.is_file():shutil.copy2(p,out/p.name)
    subprocess.run(['.deps/cc65/bin/ca65','-o',str(out/'ppu-fusion.o'),'snes/ppu_stub_fusion.asm'],check=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/ppu_register_fast.cfg','-Ln',str(out/'ppu-fusion.lbl'),
                    '-o',str(out/'ppu-fusion.bin'),str(out/'ppu-fusion.o')],check=True)
    entries = symbols(out/'ppu-fusion.lbl')
    changed,records,sites = patch(image,(out/'ppu-fusion.bin').read_bytes(),entries,labels['dispatch_write'],meta)
    (out/'native-cpu.sfc').write_bytes(changed)
    paths = [Path(__file__),Path('snes/ppu_stub_fusion.asm'),Path('snes/ppu_register_fast.cfg'),
             Path('tools/build_native.py'),Path('tools/build_inline_pitch_trial.py'),
             Path('tools/build_ppu_register_trial.py'),Path('tools/build_retained_producer_guard.py'),
             Path('.deps/cc65/bin/ca65'),Path('.deps/cc65/bin/ld65'),rom,parent/'manifest.json',
             parent/'native_runtime.lbl',out/'ppu-fusion.bin',out/'ppu-fusion.lbl']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_ppu_stub_fusion=dict(
        parent=str(parent),helper=HELPER,size=SIZE,entries=entries,targets=records,sites=sites,
        sources={str(p):sha(p) for p in paths},scope=__doc__,release_ready=False))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'],target_stubs=len(records))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):
        p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
