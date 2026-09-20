"""Reduce inactive scheduler cost and restore the exact publisher entry path."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_retained_producer_guard import symbols


def build(parent,out):
    rom=parent/'native-cpu.sfc'
    if out.exists() or sha(rom)!='28248a3aa4e57397873f899bec5cd297e102448c61cc848d01ad9eb9b737467f':
        raise ValueError('Exact3661 and fresh output required')
    meta=json.loads((parent/'manifest.json').read_text())
    for p,h in meta['experimental_audio_phase']['sources'].items():
        if sha(Path(p))!=h:raise ValueError('Changed3661 dependency')
    out.mkdir(parents=True)
    for p in parent.iterdir():
        if p.is_file():shutil.copy2(p,out/p.name)
    subprocess.run(['.deps/cc65/bin/ca65','-I','snes','-o',str(out/'fast.o'),
                    'snes/audio_phase_trial_fast.asm'],check=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/audio_phase_trial.cfg','-Ln',str(out/'fast.lbl'),
                    '-o',str(out/'fast.bin'),str(out/'fast.o')],check=True)
    old=symbols(parent/'phase.lbl');new=symbols(out/'fast.lbl')
    image=bytearray(rom.read_bytes());changes=[]
    def change(offset,before,after):
        if len(before)!=len(after) or image[offset:offset+len(before)]!=before:raise ValueError(hex(offset))
        image[offset:offset+len(after)]=after
        changes.append(dict(offset=offset,before=before.hex(),after=after.hex()))
    oldcall=b'\x22'+old['recover'].to_bytes(2,'little')+b'\xc1\xea'
    newcall=b'\x22'+new['fast_recover'].to_bytes(2,'little')+b'\xc1\xea'
    for bank in range(1,9):
        base=bank<<16
        hits=[i for i in range(base,base+65536) if image.startswith(oldcall,i)]
        if len(hits)!=43:raise ValueError('Changed enable site count')
        for i in hits:change(i,oldcall,newcall)
        change(base+0x7800,(parent/'phase.bin').read_bytes(),(out/'fast.bin').read_bytes())
    change(0x810d,bytes.fromhex('2000d9'),bytes.fromhex('209381'))
    dispatch=[i for i in range(0x8000,0x8300) if image.startswith(bytes.fromhex('5c0076c1'),i)]
    if len(dispatch)!=1:raise ValueError('Changed ordinary dispatch')
    change(dispatch[0],bytes.fromhex('5c0076c1'),b'\x5c'+new['after_publish'].to_bytes(2,'little')+b'\xc1')
    checksum(image);(out/'native-cpu.sfc').write_bytes(image)
    sources=[Path(__file__),Path('snes/audio_phase_trial_fast.asm'),Path('snes/audio_phase_trial.asm'),
             Path('snes/audio_phase_trial.cfg'),Path('tools/build_inline_pitch_trial.py'),
             Path('tools/build_retained_producer_guard.py'),Path('.deps/cc65/bin/ca65'),
             Path('.deps/cc65/bin/ld65'),rom,parent/'manifest.json',parent/'phase.bin',parent/'phase.lbl']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_audio_phase_fast=dict(
        sources={str(p):sha(p) for p in sources},changes=changes,release_ready=False,scope=__doc__))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
