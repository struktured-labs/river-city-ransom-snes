"""Execute both alias directions, queued-state immutability, full staging and ABI."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
SOURCE_ROWS=(0,1,15,30,31,32,33,47,62,63,64,65,79,94,95,96,97,111,126,127)


def expected(row,mirror,state):
    data=bytearray((i^(i>>8))&255 for i in range(8192))
    target=row^(32 if mirror else 64)
    if state==1:data[target*64:(target+1)*64]=data[row*64:(row+1)*64]
    return data


def case(core,out,row,mirror,state,source=None,word_copy=True,fastrom=False):
    out.mkdir(parents=True,exist_ok=False)
    (out/'native_palette.inc').write_text('.word '+','.join(['0']*64)+'\n')
    definitions=dict(SOURCE_ROW=row,MIRROR_MODE=mirror,
                     ALIAS_XOR=32 if mirror else 64,ALIAS_STATE=state)
    if word_copy:definitions['EXPERIMENTAL_ALIAS_WORD_COPY']=1
    if fastrom:definitions['FASTROM_TEST']=1
    flags=[part for k,v in definitions.items() for part in ('-D',f'{k}={v}')]
    subprocess.run([str(ROOT/'.deps/cc65/bin/ca65'),'-g',*flags,'-I',str(out),'-I',str(ROOT/'snes'),
        '-o',str(out/'test.o'),str(source or ROOT/'snes/alias_copy_test.asm')],check=True,capture_output=True)
    subprocess.run([str(ROOT/'.deps/cc65/bin/ld65'),'-C',str(ROOT/'snes/native_boot.cfg'),
        '-Ln',str(out/'test.lbl'),'-o',str(out/'test.bin'),str(out/'test.o')],check=True,capture_output=True)
    image=bytearray(2097152);image[0x8000:0x10000]=(out/'test.bin').read_bytes()
    image[0xffdc:0xffe0]=b'\xff\xff\0\0'
    checksum=sum(image)&65535;struct.pack_into('<HH',image,0xffdc,checksum^65535,checksum)
    (out/'test.sfc').write_bytes(image)
    result=subprocess.run([sys.executable,str(ROOT/'tools/smoke_libretro.py'),'--core',str(core),
        '--rom',str(out/'test.sfc'),'--kind','adapter','--frames','300','--ram',str(out/'memory.ram'),
        '--receipt',str(out/'receipt.json')],capture_output=True,text=True,timeout=30)
    (out/'execution.log').write_text(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError('Executed alias ABI/state failure: '+result.stderr)
    if (out/'memory.ram').read_bytes()[0x3000:0x5000]!=expected(row,mirror,state):
        raise RuntimeError('Alias snapshot changed the wrong staging bytes')


def run(core,out):
    out.mkdir(parents=True,exist_ok=False)
    for row,mirror,state in itertools.product(SOURCE_ROWS,(0,1),range(4)):
        case(core,out/f'row-{row:03d}-mirror-{mirror}-state-{state}',row,mirror,state)
    source=(ROOT/'snes/native_prepare.asm').read_text()
    negatives=[]
    for name,row,mirror,state,old,new in (
        ('wrong-mirror-destination',0,0,1,'sta a:word*2,y','sta a:word*2,x'),
        ('queued-alias-overwrite',0,0,2,'cmp #1\n.ifdef EXPERIMENTAL_ALIAS_WORD_COPY','cmp #2\n.ifdef EXPERIMENTAL_ALIAS_WORD_COPY'),
        ('lost-db-restore',0,0,1,'.endif\n    plb\n    ldx $18','.endif\n    sep #$20\n    pla\n    rep #$20\n    ldx $18')):
        if source.count(old)!=1:raise ValueError('Ambiguous alias mutation '+name)
        directory=out/name;directory.mkdir()
        fixture=directory/'alias_copy_test.asm';fixture.write_bytes((ROOT/'snes/alias_copy_test.asm').read_bytes())
        (directory/'native_prepare.asm').write_text(source.replace(old,new))
        try:case(core,directory/'run',row,mirror,state,fixture)
        except RuntimeError as error:negatives.append(dict(name=name,error=str(error)))
        else:raise ValueError('Alias mutation passed: '+name)
    report=dict(passed=True,cases=160,negative_controls=negatives,
        source_rows=SOURCE_ROWS,core_sha256=hashlib.sha256(core.read_bytes()).hexdigest(),
        checker_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        files={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file() and p.suffix in ('.json','.sfc','.ram','.asm','.log')},
        scope='All 8192 staging bytes, queued alias states 0/2/3 untouched, dirty state1 copied, source row/X/Y/D/DB and register widths. '
              'Both directions/mirroring modes, odd rows and all table boundaries; no gameplay speed claim.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=160,negative_controls=len(negatives))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.core,a.out)
