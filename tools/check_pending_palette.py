"""Execute pending-palette preparation and real consumer/CGRAM readback."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import struct
import subprocess
import sys

from tools.build_native import ROOT
from tools.benchmark_report import sha


DEFAULTS=dict(INITIALIZED=1,DEPTH=1,BANK_GUARD=0,TASK=192,GUARD=0,FLAGS=10,
              PENDING=0,STATE=0,ARMED=0,ITERATION=0,SEED=37,INTEGRATED=0,BEAM_LINE=240,
              QUEUE_READ=0,QUEUE_WRITE=0,PREVIEW_WRITE_HEAD=0,QUEUE_CONTROL=0,FADE_LEVEL=0,ALL_LEVELS=0)


def eligible(d):
    queue_safe=(d['QUEUE_READ']==d['QUEUE_WRITE'] or (d['PREVIEW_WRITE_HEAD'] and (d['ALL_LEVELS'] or d['FADE_LEVEL']==0) and
        d['QUEUE_READ']<64 and d['QUEUE_WRITE']<64 and d['QUEUE_CONTROL']<128))
    return bool(d['INITIALIZED'] and d['DEPTH']==1 and not d['BANK_GUARD'] and
        d['TASK']&192==192 and not d['GUARD']&128 and d['FLAGS']&10==10 and
        queue_safe and not d['PENDING'] and
        not (d['STATE']==0 and d['ARMED'] and d['ITERATION']))


def case(core,out,options,mutation=None):
    out.mkdir(parents=True,exist_ok=False);d=dict(DEFAULTS,**options)
    for name in ('pending_palette.asm','pending_palette_queue.inc','pending_palette_test.asm','native_video.asm'):
        source=(ROOT/'snes'/name).read_text()
        if mutation and name==mutation[0]:
            _,old,new=mutation
            if source.count(old)!=1:raise ValueError('Ambiguous pending-palette mutant')
            source=source.replace(old,new)
        (out/name).write_text(source)
    ca65,ld65=[str(ROOT/'.deps/cc65/bin'/n) for n in ('ca65','ld65')]
    subprocess.run([ca65,'-g','-D','EXPERIMENTAL_PENDING_PALETTE=1',
        *[x for k,v in d.items() for x in ('-D',f'{k}={v}')],'-I',str(out),'-I',str(ROOT/'snes'),
        '-o',str(out/'test.o'),str(out/'pending_palette_test.asm')],check=True,capture_output=True)
    subprocess.run([ld65,'-C',str(ROOT/'snes/native_boot.cfg'),'-Ln',str(out/'test.lbl'),
        '-o',str(out/'test.bin'),str(out/'test.o')],check=True,capture_output=True)
    symbols={r.split()[2].lstrip('.'):int(r.split()[1],16) for r in (out/'test.lbl').read_text().splitlines()}
    subprocess.run([ca65,'-g','-D',f'native_palette={symbols["native_palette"]}',
        *(['-D','EXPERIMENTAL_PENDING_PALETTE_WRITE_HEAD=1'] if d['PREVIEW_WRITE_HEAD'] else []),
        *(['-D','EXPERIMENTAL_PENDING_PALETTE_ALL_LEVELS=1'] if d['ALL_LEVELS'] else []),
        '-I',str(out),
        '-o',str(out/'pending.o'),str(out/'pending_palette.asm')],check=True,capture_output=True)
    subprocess.run([ld65,'-C',str(ROOT/'snes/pending_palette.cfg'),'-Ln',str(out/'pending.lbl'),
        '-o',str(out/'pending.bin'),str(out/'pending.o')],check=True,capture_output=True)
    rom=bytearray([255]*2097152);rom[0x8000:0x10000]=(out/'test.bin').read_bytes()
    rom[0x7000:0x8000]=(out/'pending.bin').read_bytes()
    rom[0xffdc:0xffe0]=b'\xff\xff\0\0';total=sum(rom)&65535
    struct.pack_into('<HH',rom,0xffdc,total^65535,total)
    (out/'test.sfc').write_bytes(rom)
    result=subprocess.run([sys.executable,'tools/smoke_libretro.py','--core',str(core),
        '--rom',str(out/'test.sfc'),'--kind','adapter','--frames','300',
        '--ram',str(out/'memory.ram'),'--receipt',str(out/'receipt.json')],
        capture_output=True,text=True,timeout=30)
    (out/'execution.log').write_text(result.stdout+result.stderr);result.check_returncode()
    ram=(out/'memory.ram').read_bytes()
    if not d['INTEGRATED'] and ram[0x6000:0x600b]!=bytes.fromhex('362534127856001eff1f00'):
        raise ValueError('Pending palette corrupted caller registers/stack')
    active=eligible(d) and (not d['INTEGRATED'] or d['BEAM_LINE'] in (240,242))
    color=lambda n: ((n&63)*509+17)&32767
    bg=[0x1234]*64;obj=[0x1234]*64
    if active:
        bg[:16]=[color((16 if i%4==0 else i)^d['SEED']) for i in range(16)]
        for i in range(16):
            value=(16+i)^d['SEED']^(0x55 if i%4==0 else 0)
            obj[(i//4)*16+i%4]=color(value)
    if (ram[0x5400:0x5480]!=struct.pack('<64H',*bg) or
            ram[0x5500:0x5580]!=struct.pack('<64H',*obj)):
        raise ValueError('Prepared palette differs or ineligible preview mutated buffers')
    original=bytes(i^d['SEED'] for i in range(32));shadow=bytes(v^0x55 for v in original)
    if ram[0x110:0x130]!=original or ram[0x13f00:0x13f20]!=shadow or ram[0x5580:0x55a0]!=shadow:
        raise ValueError('Preview modified original palette/shadow/source cache')
    if ram[0x3e]!=d['FLAGS'] or ram[0x100]!=d['TASK'] or ram[0x107]!=d['GUARD']:
        raise ValueError('Preview changed game eligibility state')
    expected=[0x1234]*256
    if active and d['INTEGRATED']:
        expected[:16]=bg[:16]
        for i in range(16):expected[128+(i//4)*16+i%4]=obj[(i//4)*16+i%4]
    if ram[0x6200:0x6400]!=struct.pack('<256H',*expected):
        raise ValueError('Actual CGRAM differs from independent expected colors')
    if d['INTEGRATED'] and active and ram[0x1c7b]:
        raise ValueError('Final batch overrun latch set')
    return dict(options=d,active=active,exit_beam=list(ram[0x1c7e:0x1c80]),
                memory_sha256=sha(out/'memory.ram'))


def run(core,out):
    out.mkdir(parents=True,exist_ok=False)
    matrix=[dict(SEED=s) for s in range(0,256,16)]
    matrix += [dict(STATE=s,ARMED=a,ITERATION=i) for s in (0,1,2) for a in (0,1) for i in (0,1)]
    matrix += [dict(**{key:v}) for key,values in dict(INITIALIZED=(0,),DEPTH=(0,2),BANK_GUARD=(1,),
        TASK=(0,64,128),GUARD=(128,),FLAGS=(0,2,8),PENDING=(1,)).items() for v in values]
    matrix += [dict(INTEGRATED=1,BEAM_LINE=line,SEED=seed) for line in (240,242,245,260) for seed in (0,37,255)]
    matrix += [dict(QUEUE_READ=r,QUEUE_WRITE=w) for r,w in ((63,0),(0,1),(63,63))]
    def execute(item):
        i,options=item;return case(core,out/f'case-{i:03d}',options)
    with ThreadPoolExecutor(max_workers=4) as pool:cases=list(pool.map(execute,enumerate(matrix)))
    negatives=[]
    for name,options,old,new in (
        ('wrong-universal-color',{},'lda f:$7E0120\n','lda f:$7E0110\n'),
        ('wrong-transparent-shadow',{},'lda f:$7F3F10+color','lda f:$7E0120+color'),
        ('ignored-dirty-flag',dict(FLAGS=2),'and #$0A\n    cmp #$0A\n    bne @return','and #$0A\n    cmp #$0A\n    nop\n    nop'),
        ('retained-iteration-preview',dict(ARMED=1,ITERATION=1),'lda a:$1CE1\n    beq @convert','lda a:$1CE1\n    bra @convert'),
        ('wrong-cgram-port',dict(INTEGRATED=1),'lda #$22\n    sta $4301','lda #$21\n    sta $4301'),
        ('ignored-command-queue',dict(QUEUE_WRITE=1),'cmp a:$06B7\n    bne @return','cmp a:$06B7\n    nop\n    nop')):
        source='native_video.asm' if name=='wrong-cgram-port' else 'pending_palette.asm'
        try:case(core,out/name,options,(source,old,new))
        except ValueError as e:negatives.append(dict(name=name,error=str(e)))
        else:raise ValueError('Pending palette mutant survived: '+name)
    report=dict(passed=True,cases=cases,negative_controls=negatives,core_sha256=sha(core),
        sources={str(p.relative_to(ROOT)):sha(p) for p in (Path(__file__),ROOT/'snes/pending_palette.asm',
            ROOT/'snes/pending_palette_test.asm',ROOT/'snes/pending_palette.cfg',ROOT/'snes/native_video.asm')},
        files={str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()
               and p.suffix in ('.asm','.json','.lbl','.ram','.sfc','.log')},
        scope='Native caller ABI, direct eligibility matrix, unchanged original/shadow/cache, '
              'prepared RGB555 and real CGRAM across early/late beam entries. '
              'Not whole-game timing, complete NMI call-graph proof or analog audio.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(cases),mutants=len(negatives))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','out'):p.add_argument('--'+name,type=Path,required=True)
    run(**vars(p.parse_args()))
