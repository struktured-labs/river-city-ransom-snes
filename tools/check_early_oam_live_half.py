"""Execute the current emitted early-OAM helper and read all544 physical OAM bytes."""
import argparse
import json
from pathlib import Path
import subprocess
from tools.build_early_oam_live_half import assemble, START
from tools.check_oam_live_half import execute,checksum
from tools.benchmark_report import sha


def check(core,out):
    out.mkdir(exist_ok=False)
    subprocess.run(['.deps/cc65/bin/ca65','-I','snes','-o',str(out/'fixture.o'),
                    'snes/early_oam_live_half_test.asm'],check=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/native_boot.cfg','-o',str(out/'fixture.bin'),str(out/'fixture.o')],check=True)
    helper=assemble();image=bytearray(2*1024*1024)
    image[0x8000:0x10000]=(out/'fixture.bin').read_bytes()
    image[START:START+len(helper)]=helper
    rom=out/'fixture.sfc';rom.write_bytes(checksum(image))
    positive=execute(core,rom,out/'positive')
    # Actual cartridge mutations, not flags fed to an abstract model.
    mutations=[('wrong-source','a200508e0243','a202508e0243',1),
               ('missing-latch','a9018df01b','a901eaeaea',1),
               ('missing-dma','8d0b42a901','eaeaeaa901',1),
               ('short-hidden','a22002ada01c','a20001ada01c',1),
               ('always-full','a200018e0543','a220028e0543',1)]
    negative=[]
    for name,before,after,case in mutations:
        a=bytes.fromhex(before);b=bytes.fromhex(after)
        if helper.count(a)!=1:raise ValueError('Nonunique mutation '+name)
        mutant=bytearray(image);mutant[START:START+len(helper)]=helper.replace(a,b)
        path=out/(name+'.sfc');path.write_bytes(checksum(mutant))
        negative.append(dict(name=name,artifacts=execute(core,path,out/name,case)))
    paths=[Path(__file__),Path('tools/build_early_oam_live_half.py'),Path('tools/check_oam_live_half.py'),
           Path('snes/early_oam_live_half.asm'),Path('snes/early_oam_live_half.cfg'),Path('snes/early_oam_live_half_test.asm'),
           Path('snes/oam_live_half.inc'),Path('snes/wram_clear.inc'),Path('snes/native_boot.cfg'),
           Path('tools/smoke_libretro.py'),core,Path('.deps/cc65/bin/ca65'),Path('.deps/cc65/bin/ld65')]
    report=dict(passed=True,generations=256,full_hidden_generations=4,positive=positive,negative=negative,
        sources={str(p):sha(p) for p in paths},release_ready=False,
        scope=__doc__+' Poisoned hardware, all live bytes change each generation, static tail changes in hidden generations. Not gameplay timing or proof of all staging writers.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,generations=256,rejected_mutants=len(negative))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('core','out'):p.add_argument('--'+k,type=Path,required=True)
    check(**vars(p.parse_args()))
