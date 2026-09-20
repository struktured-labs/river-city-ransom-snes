"""Executed hidden-sprite deferral, refresh, and actual OAM oracle."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import itertools
import json
from pathlib import Path
import struct
import subprocess
import sys

from tools.benchmark_report import sha
ROOT=Path(__file__).resolve().parents[1]
DEFAULTS=dict(INITIALIZED=1,STATE=2,CURSOR=12,ROW_FLAG=1,REQUIRED=1,HALF=0,SEED=37,PIPELINE=0)


def eligible(d):
    return bool(d['INITIALIZED'] and d['STATE']==2 and d['ROW_FLAG']==1 and d['REQUIRED'])


def case(core,out,options,mutation=None):
    out.mkdir(parents=True,exist_ok=False);d=dict(DEFAULTS,**options)
    for name in ('native_prepare.asm','native_video.asm','hidden_sprite_test.asm'):
        source=(ROOT/'snes'/name).read_text()
        if mutation and name==mutation[0]:
            _,old,new=mutation
            if source.count(old)!=1:raise RuntimeError('Ambiguous sprite mutant')
            source=source.replace(old,new)
        (out/name).write_text(source)
    (out/'native_palette.inc').write_text('.word '+','.join(['0']*64)+'\n')
    defs=dict(d,EXPERIMENTAL_HIDDEN_SPRITE_DEFER=1,EXPERIMENTAL_SPRITE_DELTA=1,
        EXPERIMENTAL_OAM_DIRTY_GATE=1,EXPERIMENTAL_CHR_DIRTY_GATE=1,EXPERIMENTAL_TRANSITION_SCAN=1)
    subprocess.run([str(ROOT/'.deps/cc65/bin/ca65'),'-g',*[s for k,v in defs.items() for s in ('-D',f'{k}={v}')],
        '-I',str(out),'-I',str(ROOT/'snes'),'-o',str(out/'test.o'),str(out/'hidden_sprite_test.asm')],check=True,capture_output=True)
    subprocess.run([str(ROOT/'.deps/cc65/bin/ld65'),'-C',str(ROOT/'snes/native_boot.cfg'),'-Ln',str(out/'test.lbl'),
        '-o',str(out/'test.bin'),str(out/'test.o')],check=True,capture_output=True)
    rom=bytearray([255]*2097152);rom[0x8000:0x10000]=(out/'test.bin').read_bytes()
    rom[0xffdc:0xffe0]=b'\xff\xff\0\0';checksum=sum(rom)&65535
    struct.pack_into('<HH',rom,0xffdc,checksum^65535,checksum);(out/'test.sfc').write_bytes(rom)
    result=subprocess.run([sys.executable,str(ROOT/'tools/smoke_libretro.py'),'--core',str(core),
        '--rom',str(out/'test.sfc'),'--kind','adapter','--frames','120','--ram',str(out/'memory.ram'),
        '--receipt',str(out/'receipt.json')],capture_output=True,text=True,timeout=30)
    (out/'execution.log').write_text(result.stdout+result.stderr);result.check_returncode()
    ram=(out/'memory.ram').read_bytes();source=bytes(i^d['SEED'] for i in range(256))
    wanted=bytearray([0x55]*544)
    for i in range(64):
        y,tile,attr,x=source[i*4:i*4+4]
        # Native visible range and bit translation, independently per sprite.
        wanted[i*4:i*4+4]=bytes((x,y+2 if y<239 else 240,tile,
            (attr&0xc0)|((attr&3)<<1)|(0 if attr&32 else 48)|((d['HALF']>>3)&1)))
    if not d['INITIALIZED']:
        for i in range(64,128):wanted[i*4+1]=240
        wanted[512:544]=bytes(32)
    if ram[0x5000:0x5220]!=wanted:raise ValueError('Final sprite conversion differs')
    if ram[0x6500:0x6720]!=wanted:raise ValueError('Actual OAM differs')
    if d['PIPELINE'] and ram[0x6402:0x6404]!=bytes((2,0)):
        raise ValueError('Publisher revealed too early or failed to retire ready generation')
    if ram[0x5600:0x5700]!=source or ram[0x1000:0x1100]!=source:raise ValueError('Source/cache differs')
    if eligible(d):
        if ram[0x6000:0x6220]!=bytes([0x55]*544) or ram[0x6300:0x6400]!=bytes([0xcc]*256):
            raise ValueError('Blocked hidden sprites were prepared early')
        if ram[0x6400:0x6402]!=bytes((1,0)):raise ValueError('Deferred producer lost dirtiness or changed pattern cache')
    elif ram[0x6000:0x6220]!=wanted:raise ValueError('Nonblocked sprites were incorrectly deferred')
    return dict(options=d,deferred=eligible(d),rom_sha256=sha(out/'test.sfc'),ram_sha256=sha(out/'memory.ram'))


def run(core,out):
    out.mkdir(parents=True,exist_ok=False)
    files=[Path(__file__),*[ROOT/'snes'/n for n in ('hidden_sprite_test.asm','native_prepare.asm','native_video.asm','sprite_delta.inc','wram_clear.inc')]]
    sources={str(p):sha(p) for p in files}
    matrix=[dict(CURSOR=c,HALF=h,SEED=s) for c,h,s in itertools.product((0,12,29,63,64,125,127,255),(0,8),(0,37,255))]
    matrix += [dict(STATE=state,ROW_FLAG=flag,REQUIRED=req,INITIALIZED=init)
        for state,flag,req,init in itertools.product((0,1,2),range(4),(0,1),(0,1))]
    matrix += [dict(PIPELINE=1,CURSOR=c,HALF=h) for c,h in itertools.product((0,12,29,64,125),(0,8))]
    def execute(item):
        i,d=item;return case(core,out/f'case-{i:03d}',d)
    with ThreadPoolExecutor(max_workers=4) as pool:cases=list(pool.map(execute,enumerate(matrix)))
    mutants=[]
    for name,options,file,old,new in (
        ('queued-row-deferred',dict(ROW_FLAG=2),'native_prepare.asm','lda $1D00,x\n    cmp #1\n    bne @sprite_work','lda $1D00,x\n    cmp #2\n    bne @sprite_work'),
        ('nonrequired-row-deferred',dict(REQUIRED=0),'native_prepare.asm','lda $1E80,x\n    beq @sprite_work','lda $1E80,x\n    nop\n    nop'),
        ('initialization-skipped',dict(INITIALIZED=0),'native_prepare.asm','lda $1C79\n    beq @sprite_work','lda $1C79\n    nop\n    nop'),
        ('dirty-latch-lost',{},'native_prepare.asm','    jmp prepare_tail\n@sprite_work:',
            '    stz $1C87\n    jmp prepare_tail\n@sprite_work:'),
        ('early-reveal',dict(PIPELINE=1),'native_video.asm','transition_ready:\n    .a8',
            'transition_ready:\n    .a8\n    stz $1CA0')):
        try:case(core,out/name,options,(file,old,new))
        except ValueError as error:mutants.append(dict(name=name,error=str(error)))
        else:raise ValueError('Unsafe sprite mutant survived: '+name)
    if sources!={str(p):sha(p) for p in files}:raise ValueError('Sources changed during sprite oracle')
    report=dict(passed=True,cases=cases,mutants=mutants,sources=sources,core_sha256=sha(core),
        scope='Actual OAM and prepared sprite/cache bytes; deferred calls preserve old snapshot and dirtiness, '
              'subsequent unblocked call refreshes current sprites. Ten real-publisher cases retain hidden state '
              'until required rows are queued, then retire them and publish fresh OAM.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS',len(cases),len(mutants))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','out'):p.add_argument('--'+name,type=Path,required=True)
    run(**vars(p.parse_args()))
