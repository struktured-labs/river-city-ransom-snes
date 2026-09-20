"""Execute whole original/fused PPU stubs, with actual coroutine returns and NMI policy."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_ppu_register_trial import HELPER,SIZE
from tools.build_retained_producer_guard import symbols


def execute(candidate,core,out,case,mutation=None):
    out.mkdir(parents=True)
    resume = case['RESUME']
    segment = f'RETURN: load=ROM,type=ro,start=${resume:04X}; ' if resume else ''
    (out/'test.cfg').write_text('MEMORY { ROM: start=$8500,size=$7B00,file=%O,fill=yes,fillval=$FF; }\n'
        'SEGMENTS { CODE: load=ROM,type=ro; '+segment+'HEADER: load=ROM,type=ro,start=$FFC0; '
        'VECTORS: load=ROM,type=ro,start=$FFE0; }\n')
    subprocess.run(['.deps/cc65/bin/ca65',*[v for k,n in case.items() for v in ('-D',f'{k}={n}')],
        '-I','snes','-o',str(out/'test.o'),'snes/ppu_stub_test.asm'],check=True,capture_output=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C',str(out/'test.cfg'),'-Ln',str(out/'test.lbl'),
                    '-o',str(out/'test.bin'),str(out/'test.o')],check=True,capture_output=True)
    program = (out/'test.bin').read_bytes()
    production = (candidate/'native-cpu.sfc').read_bytes()
    image = bytearray(0x200000)
    for bank in range(9):
        base = bank*65536;source = (bank or 1)*65536
        image[base+0x2000:base+0x8000] = production[source+0x2000:source+0x8000]
        image[base+0x8500:base+65536] = program
    if mutation:
        needle,replacement = map(bytes.fromhex,mutation)
        if len(needle)!=len(replacement):
            raise ValueError('Mutation size changed')
        for bank in range(1,9):
            at = bank*65536+HELPER
            body = image[at:at+SIZE]
            if body.count(needle)!=1:raise ValueError('Ambiguous mutation')
            index = at+body.index(needle)
            image[index:index+len(needle)] = replacement
    checksum(image)
    (out/'test.sfc').write_bytes(image)
    run = subprocess.run([sys.executable,'-m','tools.smoke_libretro','--core',str(core),
        '--rom',str(out/'test.sfc'),'--kind','adapter','--frames','120','--ram',str(out/'memory.ram'),
        '--receipt',str(out/'receipt.json')],capture_output=True,text=True,timeout=30)
    (out/'execution.log').write_text(run.stdout+run.stderr)
    if run.returncode:raise ValueError('Full-stub fixture failed: '+run.stderr[-400:])
    return (out/'memory.ram').read_bytes()


def independent(ram,c):
    if len(ram)!=131072:
        raise ValueError('Incomplete WRAM')
    expected = bytearray(b'\x5a'*0x300)
    def put(address,value):expected[address-0x1b00] = value
    for address,value in ((0x1c20,c['OLD_CTRL']),(0x1c25,c['LATCH']),(0x1c27,0x20),(0x1c26,0x1f),
        (0x1c18,0),(0x1c06,0),(0x1c60,1),(0x1c61,0),(0x1c0a,c['DEPTH']),(0x1c83,c['PAIR'])):
        put(address,value)
    value = c[{0x8d:'INPUT_A',0x8e:'INPUT_X',0x8c:'INPUT_Y'}[c['OPCODE']]]
    register = c['ADDRESS']&7
    put(0x1b20,c['ADDRESS']&255);put(0x1b21,c['ADDRESS']>>8);put(0x1b22,value)
    if register==0:
        if (c['OLD_CTRL']^value)&24:put(0x1cbb,1)
        put(0x1c20,value)
    elif register==3:put(0x1c23,value)
    elif register==5:
        put(0x1c28+c['LATCH'],value);put(0x1c25,c['LATCH']^1)
    elif c['LATCH']:put(0x1c26,value);put(0x1c25,0)
    else:put(0x1c27,value&63);put(0x1c25,1)
    actual = bytearray(ram[0x1b00:0x1e00])
    for offset in (0x162,0x163,0x16a):actual[offset] = expected[offset]
    if actual!=expected:raise ValueError('Independent PPU/mailbox/scratch mismatch')
    abi = bytes((c['INPUT_A'],0x1b,c['FLAGS']|0x30,c['INPUT_X'],c['INPUT_Y'],0x34,0x12,0x83,c['STACK']))
    if ram[0x6000:0x6009]!=abi:raise ValueError('Full-stub A/B/P/X/Y/D/DB/SP mismatch')
    if c['RESUME']:
        enabled = bool(value&128) and (not c['DEPTH'] or not c['TASK'])
        immediate = False  # original coroutine waits out pending VBlank
        blank = c['WAITLINE']>=240 and not enabled
    else:
        enabled = bool(c['OLD_CTRL']&128) and not (c['DEPTH'] or c['PAIR'])
        immediate = enabled and c['WAITLINE']>=240
        blank = c['WAITLINE']>=240
    if bool(ram[0x1c6a])!=enabled or ram[0x600a]!=int(immediate) or ram[0x600b]!=128*blank:
        raise ValueError('Actual NMI enable/pending/coroutine wait policy mismatch: '+
                         str((ram[0x1c6a],ram[0x600a],ram[0x600b],enabled,immediate,blank)))
    return dict(enabled=enabled,pending_delivered=immediate,return_in_vblank=blank)


def matrix(targets):
    values = (0,1,7,8,15,16,23,24,31,32,63,64,127,128,254,255)
    cases = []
    def add(row,value,old,latch,depth,pair,task,line,flags):
        c = dict(STUB=row['start'],RESUME=row['resume'] or 0,ADDRESS=row['address'],OPCODE=row['opcode'],
            INPUT_A=value if row['opcode']==0x8d else 0x57,INPUT_X=value if row['opcode']==0x8e else 0xa6,
            INPUT_Y=value if row['opcode']==0x8c else 0x59,OLD_CTRL=old,LATCH=latch,DEPTH=depth,PAIR=pair,
            TASK=task,WAITLINE=line,FLAGS=flags,BANK=0xc1+len(cases)%8,STACK=(0x20,0x80,0xff)[len(cases)%3])
        cases.append(c)
    for row in targets:
        for i,value in enumerate(values):
            add(row,value,value if i&1 else value^24,i&1,1,0,0xc0,40,
                (0x35,0x77,0xbd,0xff)[i%4])
        for depth,pair,task in ((0,0,0xc0),(1,0,0xc0),(0,1,0xc0),(1,1,0)):
            for line in (40,241):
                add(row,0x80,0x80,1,depth,pair,task,line,0x31)
    return cases


def audit(parent,candidate,core,out):
    if out.exists():raise ValueError('Fresh output required')
    meta = json.loads((candidate/'manifest.json').read_text())
    sources = dict(meta['experimental_ppu_stub_fusion']['sources'])
    for p,d in sources.items():
        if sha(Path(p))!=d:raise ValueError('Changed implementation source')
    for root in (parent,candidate):
        if sha(root/'native-cpu.sfc')!=json.loads((root/'manifest.json').read_text())['rom_sha256']:
            raise ValueError('Changed cartridge')
    cases = matrix(meta['experimental_ppu_stub_fusion']['targets'])
    out.mkdir(parents=True)
    def check(item):
        i,c = item;folder = out/f'case-{i:03}'
        old = execute(parent,core,folder/'before',c)
        new = execute(candidate,core,folder/'after',c)
        excluded = set(range(0x100,0x200))|{0x1c62,0x1c63}
        mismatch = [i for i,(a,b) in enumerate(zip(old,new)) if a!=b and i not in excluded]
        if len(old)!=131072 or len(new)!=131072 or mismatch:
            raise ValueError('Full WRAM mismatch: '+str((i,c,mismatch[:20])))
        behavior = independent(new,c)
        return dict(case=c,behavior=behavior,artifacts={str(p):sha(p)
            for p in folder.rglob('*') if p.suffix in ('.sfc','.ram','.json','.lbl')})
    with ThreadPoolExecutor(max_workers=6) as pool:results = list(pool.map(check,enumerate(cases)))
    mutations = [('wrong-high-mask',next(c for c in cases if c['ADDRESS']==0x2006 and c['INPUT_A']==254),('293f','297f')),
        ('lost-chr-dirty',cases[0],('8dbb1c','eaeaea')),
        ('wrong-scroll-toggle',next(c for c in cases if c['ADDRESS']==0x2005),('4901','4900')),
        ('lost-hidden-b',cases[0],('a91beb','a91bea'))]
    mutants = []
    for name,c,mutation in mutations:
        ram = execute(candidate,core,out/name,c,mutation)
        try:independent(ram,c)
        except ValueError as exc:mutants.append(dict(name=name,rejected=True,reason=str(exc)))
        else:raise ValueError('Mutant survived: '+name)
    paths = [Path(__file__),Path('snes/ppu_stub_test.asm'),Path('snes/wram_clear.inc'),
             Path('tools/smoke_libretro.py'),core,*[root/name for root in (parent,candidate)
             for name in ('native-cpu.sfc','manifest.json','native_runtime.lbl')]]
    sources.update({str(p):sha(p) for p in paths})
    report = dict(passed=True,cases=results,mutants=mutants,sources=sources,release_ready=False,
        scope=__doc__+' Independent masked/pending/ordinary and coroutine wait policies. '
        'Fixture redirects only original resume destinations into its ABI recorder. '
        'It does not execute the subsequent original coroutine task body.',
        mutant_artifacts={str(p):sha(p) for m in mutants for p in (out/m['name']).iterdir()
                          if p.suffix in ('.sfc','.ram','.json','.lbl')})
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(cases),mutants=len(mutants))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent','candidate','core','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
