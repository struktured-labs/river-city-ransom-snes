"""Execute actual guard bytes at beam boundaries and wrapped emulation stacks.

Downstream producers are dispatch spies, not real graphics or NMI handlers.
This proves guard/ABI/ownership decisions, not full-game interrupt timing.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_retained_producer_guard import HELPER,symbols


def execute(core,candidate,out,line,stack,pending,ordinary,entry,bank,mutant=False):
    out.mkdir(parents=True,exist_ok=False)
    labels=symbols(candidate/'native_runtime.lbl');entries=symbols(candidate/'retained-guard.lbl')
    data=(candidate/'retained-guard.bin').read_bytes()
    if mutant:
        if data.count(bytes.fromhex('bd0001'))!=2:raise ValueError('Wrong stack mutation preimage')
        data=data.replace(bytes.fromhex('bd0001'),bytes.fromhex('bd0002'))
    (out/'retained-guard.bin').write_bytes(data)
    config=('MEMORY { ROM: start=$2000,size=$E000,file=%O,fill=yes,fillval=$FF; }\n'
        f'SEGMENTS {{ PREPARE: load=ROM,type=ro,start=${labels["second_tick_prepare"]:04x}; '
        f'FALLBACK: load=ROM,type=ro,start=${labels["second_tick_prepare_fallback"]:04x}; '
        f'GUARD: load=ROM,type=ro,start=${HELPER:04x}; '
        'CODE: load=ROM,type=ro,start=$8500; HEADER: load=ROM,type=ro,start=$FFC0; VECTORS: load=ROM,type=ro,start=$FFE0; }\n')
    (out/'test.cfg').write_text(config)
    defs=dict(TARGET_LINE=line,STACK=stack,PENDING=pending,ORDINARY=ordinary,
        CAMERA_RETURN=labels['camera_deferred_nmi_return'],BANK=bank,
        GUARD_ENTRY=entries['guarded_'+entry])
    subprocess.run(['.deps/cc65/bin/ca65',*[v for k,n in defs.items() for v in ('-D',f'{k}={n}')],
        '-I','snes','--bin-include-dir',str(out),'-o',str(out/'test.o'),
        'snes/retained_producer_guard_test.asm'],check=True,capture_output=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C',str(out/'test.cfg'),'-o',str(out/'test.bin'),
                    str(out/'test.o')],check=True,capture_output=True)
    program=(out/'test.bin').read_bytes()
    if len(program)!=0xe000 or program[HELPER-0x2000:HELPER-0x2000+256]!=data:
        raise ValueError('Fixture relocated or changed helper bytes')
    image=bytearray(0x200000)
    for b in range(9):image[b*65536+0x2000:(b+1)*65536]=program
    checksum(image);(out/'test.sfc').write_bytes(image)
    run=subprocess.run([sys.executable,'-m','tools.smoke_libretro','--core',str(core),
        '--rom',str(out/'test.sfc'),'--kind','adapter','--frames','120',
        '--ram',str(out/'memory.ram'),'--receipt',str(out/'receipt.json')],
        capture_output=True,text=True,timeout=30,check=True)
    (out/'execution.log').write_text(run.stdout+run.stderr)
    ram=(out/'memory.ram').read_bytes();ret=labels['camera_deferred_nmi_return']+ordinary
    expected=bytes((0x56,0x78,(stack-6)&255,0x34,0x12,0x82,0x78,0x56,0x40,0x35,
                    ret&255,ret>>8,stack))
    if ram[0x6000:0x600d]!=expected:
        raise ValueError('Guard corrupted X/Y/SP/DP/DB/saved frame: '+ram[0x6000:0x600d].hex())
    deferred=bool(pending and not ordinary and line>=194)
    wanted=bytes((pending if deferred else 0,0 if deferred else (1 if entry=='fallback' else 2)))
    matched=ram[0x600d:0x600f]==wanted
    if matched==mutant:raise ValueError('Wrong decision or surviving stack mutant')
    return dict(line=line,stack=stack,pending=pending,ordinary=ordinary,entry=entry,bank=bank,
        deferred=deferred,actual=list(ram[0x600d:0x600f]),mutant_rejected=mutant,
        artifacts={str(p):sha(p) for p in (out/'test.sfc',out/'memory.ram',out/'receipt.json')})


def audit(candidate,core,out):
    if out.exists():raise ValueError('Fresh output required')
    meta=json.loads((candidate/'manifest.json').read_text())
    spec=meta['experimental_retained_producer_guard']
    for p,h in spec['sources'].items():
        if sha(Path(p))!=h:raise ValueError('Changed guard source')
    image=(candidate/'native-cpu.sfc').read_bytes();helper=(candidate/'retained-guard.bin').read_bytes()
    if sha(candidate/'native-cpu.sfc')!=meta['rom_sha256']:raise ValueError('Changed candidate')
    for bank in range(1,9):
        if image[bank*65536+HELPER:bank*65536+HELPER+256]!=helper:raise ValueError('Different deployed helper')
    for site in spec['sites']:
        if image[site['site']:site['site']+3]!=b'\x20'+site['replacement'].to_bytes(2,'little'):
            raise ValueError('Wrong guard callsite')
    matrix=[]
    for stack in (*range(12),127,250,251,252,253,254,255):
        for entry in ('fallback','prepare'):matrix.append((230,stack,1,0,entry))
    for line in (0,190,193,194,239,250,256,260):
        for entry in ('fallback','prepare'):matrix.append((line,255,1,0,entry))
    for pending,ordinary in ((0,0),(1,1),(0,1)):
        for entry in ('fallback','prepare'):matrix.append((230,0,pending,ordinary,entry))
    out.mkdir(parents=True)
    def run(item):
        i,params=item
        return execute(core,candidate,out/f'case-{i:03}',*params,0xc1+i%8)
    with ThreadPoolExecutor(max_workers=6) as pool:cases=list(pool.map(run,enumerate(matrix)))
    mutants=[execute(core,candidate,out/('wrong-page-'+entry),230,0,1,0,entry,0xc1,True)
             for entry in ('fallback','prepare')]
    paths=[Path(__file__),Path('tools/build_retained_producer_guard.py'),
        Path('snes/retained_producer_guard_test.asm'),Path('snes/retained_producer_guard.asm'),
        Path('tools/smoke_libretro.py'),Path('snes/wram_clear.inc'),
        Path('tools/build_inline_pitch_trial.py'),core,candidate/'manifest.json',
        candidate/'native-cpu.sfc',candidate/'retained-guard.bin',candidate/'retained-guard.lbl',
        candidate/'native_runtime.lbl',Path('.deps/cc65/bin/ca65'),Path('.deps/cc65/bin/ld65')]
    report=dict(passed=True,cases=cases,mutants=mutants,scope=__doc__,release_ready=False,
        sources={str(p):sha(p) for p in paths})
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(cases),mutants=len(mutants))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','core','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
