"""Execute production palette hook against its original scalar adapter path."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import itertools
import json
from pathlib import Path
import struct
import subprocess
import sys

from tools.build_native import stub, ROOT
from tools.benchmark_report import sha


def case(core,out,options,mutation=None):
    out.mkdir(parents=True,exist_ok=False)
    helper=(ROOT/'snes/palette_copy.inc').read_text()
    if mutation:
        old,new=mutation
        if helper.count(old)!=1:raise ValueError('Ambiguous palette mutant')
        helper=helper.replace(old,new)
    (out/'palette_copy.inc').write_text(helper)
    # Include resolution is relative to the runtime file first.
    (out/'native_runtime.asm').write_bytes((ROOT/'snes/native_runtime.asm').read_bytes())
    ca65,ld65=[str(ROOT/'.deps/cc65/bin'/n) for n in ('ca65','ld65')]
    subprocess.run([ca65,'-g','-D','EXPERIMENTAL_PALETTE_COPY=1',
        '-D','audio_publish_bridge=32512','-D','video_prepare_bridge=32512',
        '-I',str(out),'-I',str(ROOT/'snes'),'-o',str(out/'runtime.o'),str(out/'native_runtime.asm')],
        capture_output=True,check=True)
    subprocess.run([ld65,'-C',str(ROOT/'snes/native_runtime.cfg'),'-Ln',str(out/'runtime.lbl'),
        '-o',str(out/'runtime.bin'),str(out/'runtime.o')],capture_output=True,check=True)
    symbols={r.split()[2].lstrip('.'):int(r.split()[1],16)
             for r in (out/'runtime.lbl').read_text().splitlines()}
    io=stub(0x8d,0x2007,symbols['dispatch_ppudata'],fast_ppudata=True)
    memories=[]
    for fast in (False,True):
        folder=out/str(int(fast));folder.mkdir()
        defs=dict(SEED=options.get('seed',73),CTRL=options.get('ctrl',128),
            ADDRESS=options.get('address',0x3f00),DEPTH=options.get('depth',1),
            BANK_GUARD=options.get('bank_guard',0),COUNT=options.get('count',239),
            FLAGS=options.get('flags',0x74),START_X=options.get('x',0),FAST=int(fast),
            palette_copy_loop=symbols['palette_copy_loop'],io_write_stub=0x6000)
        subprocess.run([ca65,'-g',*[a for k,v in defs.items() for a in ('-D',f'{k}={v}')],
            '-I',str(ROOT/'snes'),'-o',str(folder/'test.o'),str(ROOT/'snes/palette_copy_test.asm')],
            capture_output=True,check=True)
        subprocess.run([ld65,'-C',str(ROOT/'snes/palette_copy_test.cfg'),'-Ln',str(folder/'test.lbl'),
            '-o',str(folder/'test.bin'),str(folder/'test.o')],capture_output=True,check=True)
        image=bytearray([255]*2097152);program=(folder/'test.bin').read_bytes()
        image[0x8000:0x10000]=program
        for bank in range(1,9):
            image[bank*65536+0x8000:(bank+1)*65536]=program
            image[bank*65536+0x2000:bank*65536+0x6000]=(out/'runtime.bin').read_bytes()
            image[bank*65536+0x6000:bank*65536+0x6000+len(io)]=io
        image[0xffdc:0xffe0]=b'\xff\xff\0\0';s=sum(image)&65535
        struct.pack_into('<HH',image,0xffdc,s^65535,s)
        (folder/'test.sfc').write_bytes(image)
        command=[sys.executable,str(ROOT/'tools/smoke_libretro.py'),'--core',str(core),
            '--rom',str(folder/'test.sfc'),'--kind','adapter','--frames','300',
            '--ram',str(folder/'memory.ram'),'--receipt',str(folder/'receipt.json')]
        result=subprocess.run(command,capture_output=True,text=True,timeout=30)
        (folder/'execution.log').write_text(result.stdout+result.stderr)
        result.check_returncode()
        memories.append((folder/'memory.ram').read_bytes())
    before,after=memories
    regions=((0x6000,0x600a),(0x1c09,0x1c0b),(0x1c20,0x1c2b),
             (0x1c83,0x1c86),(0x1d00,0x1e00),(0x10000,0x14000),(0x110,0x130))
    for a,b in regions:
        if before[a:b]!=after[a:b]:
            raise ValueError(f'Palette copy differs in {a:04x}..{b:04x}: '
                             f'{before[a:b].hex()[:80]} vs {after[a:b].hex()[:80]}')
    eligible=(defs['START_X']==0 and defs['ADDRESS']==0x3f00 and not defs['CTRL']&4
              and not defs['FLAGS']&8 and (defs['DEPTH'] or defs['BANK_GUARD'] or not defs['CTRL']&128))
    if eligible:
        expected=bytearray((i^defs['SEED']^0xa5)&255 for i in range(256))
        for i in range(32):expected[i-16 if i in (16,20,24,28) else i]=i^defs['SEED']
        if after[0x13f00:0x14000]!=expected:raise ValueError('Independent palette alias oracle failed')
        if after[0x1c09]!=(defs['COUNT']+32)&255:raise ValueError('Write count differs')
    return dict(options=options,eligible=bool(eligible),caller=after[0x6000:0x600a].hex(),
                roms=[sha(out/str(i)/'test.sfc') for i in (0,1)])


def run(core,out):
    out.mkdir(parents=True,exist_ok=False)
    sources=[Path(__file__),ROOT/'snes/palette_copy.inc',ROOT/'snes/native_runtime.asm',
             ROOT/'snes/palette_copy_test.asm',ROOT/'snes/palette_copy_test.cfg',ROOT/'tools/build_native.py']
    hashes={str(p.relative_to(ROOT)):sha(p) for p in sources}
    matrix=[dict(seed=s,flags=f,count=c,ctrl=ctrl,depth=d,bank_guard=b)
            for s,f,c,(ctrl,d,b) in itertools.product((0,73,128,255),(0x34,0x74),(0,239),
                                                     ((0,0,0),(128,1,0),(128,0,1)))]
    matrix += [dict(x=x) for x in (1,31,32,255)]
    matrix += [dict(address=a) for a in (0x3f01,0x3f20,0x3fff,0x2000)]
    matrix += [dict(ctrl=132),dict(flags=0x7c),dict(ctrl=128,depth=0)]
    def execute(item):
        i,options=item
        return case(core,out/f'case-{i:03d}',options)
    with ThreadPoolExecutor(max_workers=4) as pool:cases=list(pool.map(execute,enumerate(matrix)))
    negatives=[]
    for name,options,mutation in (
        ('wrong-alias',{},('sta f:$7F3F00+color-16','sta f:$7F3F00+color')),
        ('wrong-count',{},('adc #32','adc #31')),
        ('lost-overflow',{},('    plp\n    lda a:$012F','    plp\n    clv\n    lda a:$012F')),
        ('wrong-address',{},('lda #$20\n    sta a:$1C26','lda #$21\n    sta a:$1C26')),
        ('ignored-stride',dict(ctrl=132),('and #4\n    bne @fallback','and #4\n    nop\n    nop'))):
        try:case(core,out/name,options,mutation)
        except ValueError as error:negatives.append(dict(name=name,error=str(error)))
        else:raise ValueError('Palette mutant survived: '+name)
    if hashes!={str(p.relative_to(ROOT)):sha(p) for p in sources}:raise ValueError('Source changed during run')
    report=dict(passed=True,cases=cases,negative_controls=negatives,core_sha256=sha(core),sources=hashes,
        files={str(p.relative_to(out)):sha(p) for p in out.rglob('*')
               if p.is_file() and p.suffix in ('.sfc','.ram','.lbl','.json','.asm','.inc','.log')},
        scope='Real production adapter versus hooked loop, independent eligible palette aliases, '
              'register/hidden-B/DP/DB/PB/stack, counters and untouched graphics state. '
              'Unowned NMI configuration takes scalar fallback; not a hardware interrupt-race proof.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(cases),mutants=len(negatives))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','out'):p.add_argument('--'+name,type=Path,required=True)
    run(**vars(p.parse_args()))
