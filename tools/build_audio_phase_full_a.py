"""Repair the executed phase80 hidden-accumulator corruption without changing tick ownership."""
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
    if out.exists() or sha(rom)!='66b6d8d24316f8f71d699fa1eb1fc549d98a31c1a6c1907534468289fb5fe98b':
        raise ValueError('Exact3665 and fresh output required')
    out.mkdir(parents=True)
    for p in parent.iterdir():
        if p.is_file():shutil.copy2(p,out/p.name)
    subprocess.run(['.deps/cc65/bin/ca65','-o',str(out/'full-a.o'),'snes/audio_phase_full_a.asm'],check=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/audio_phase_full_a.cfg','-Ln',str(out/'full-a.lbl'),
                    '-o',str(out/'full-a.bin'),str(out/'full-a.o')],check=True)
    labels=symbols(out/'full-a.lbl');original=rom.read_bytes();image=bytearray(original);changes=[]
    def change(at,before,after):
        if len(before)!=len(after) or image[at:at+len(before)]!=before:raise ValueError(hex(at))
        image[at:at+len(after)]=after;changes.append(dict(offset=at,before=before.hex(),after=after.hex()))
    for old,label,count in [('220078c1','arm_full_a',9),('225878c1','drain_full_a',9),
                            ('5c9a78c1','recover_full_a',8),('5c1b79c1','irq_full_a',1)]:
        before=bytes.fromhex(old);hits=[i for i in range(len(original)) if original.startswith(before,i)]
        if len(hits)!=count:raise ValueError(f'{old}: expected{count}, got{len(hits)}')
        for at in hits:change(at,before,before[:1]+labels[label].to_bytes(2,'little')+b'\xc1')
    block=(out/'full-a.bin').read_bytes()
    for bank in range(1,9):change((bank<<16)+0x79a0,b'\xff'*len(block),block)
    checksum(image);(out/'native-cpu.sfc').write_bytes(image)
    meta=json.loads((parent/'manifest.json').read_text())
    sources=[Path(__file__),Path('snes/audio_phase_full_a.asm'),Path('snes/audio_phase_full_a.cfg'),
             Path('tools/build_inline_pitch_trial.py'),Path('tools/build_retained_producer_guard.py'),
             Path('.deps/cc65/bin/ca65'),Path('.deps/cc65/bin/ld65'),rom,parent/'manifest.json']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_audio_phase_full_a=dict(
        sources={str(p):sha(p) for p in sources},changes=changes,labels=labels,release_ready=False,scope=__doc__))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'],labels=labels)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
