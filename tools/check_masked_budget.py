"""Execute both actual admission helpers; test ownership/ABI, not worst-case timing."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_retained_producer_guard import symbols
from tools.build_masked_budget_trial import CUTOFF,REGIONS


def execute(core,candidate,out,line,stack,pending,ordinary,entry,bank,mutant=False):
    out.mkdir(parents=True,exist_ok=False)
    labels=symbols(candidate/'native_runtime.lbl');entries=symbols(candidate/'retained-guard.lbl')
    for _,_,name,needle in REGIONS:
        data=(candidate/name).read_bytes()
        current=needle[:1]+bytes((CUTOFF,))+needle[2:]
        if data.count(current)!=1:raise ValueError('Wrong admission immediate')
        if mutant:data=data.replace(current,needle)
        (out/name).write_bytes(data)
    (out/'test.asm').write_text('.include "retained_producer_guard_test.asm"\n'
        '.segment "SERVICE"\n lda #3\n sta f:$7E600E\n stz a:$1B80\n rts\n'
        '.segment "CAMERA"\n .incbin "guard.bin"\n')
    (out/'test.cfg').write_text('MEMORY { ROM: start=$2000,size=$E000,file=%O,fill=yes,fillval=$FF; }\n'
        f'SEGMENTS {{ PREPARE: load=ROM,type=ro,start=${labels["second_tick_prepare"]:04x}; '
        f'SERVICE: load=ROM,type=ro,start=${labels["second_tick_prepare_service"]:04x}; '
        f'FALLBACK: load=ROM,type=ro,start=${labels["second_tick_prepare_fallback"]:04x}; '
        'GUARD: load=ROM,type=ro,start=$7B00; CAMERA: load=ROM,type=ro,start=$7F00; '
        'CODE: load=ROM,type=ro,start=$8500; HEADER: load=ROM,type=ro,start=$FFC0; '
        'VECTORS: load=ROM,type=ro,start=$FFE0; }\n')
    defs=dict(TARGET_LINE=line,STACK=stack,PENDING=pending,ORDINARY=ordinary,
        CAMERA_RETURN=labels['camera_deferred_nmi_return'],BANK=bank,
        GUARD_ENTRY=0x7f00 if entry=='camera' else entries['guarded_'+entry])
    subprocess.run(['.deps/cc65/bin/ca65',*[v for k,n in defs.items() for v in ('-D',f'{k}={n}')],
        '-I','snes','--bin-include-dir',str(out),'-o',str(out/'test.o'),str(out/'test.asm')],
        check=True,capture_output=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C',str(out/'test.cfg'),'-o',str(out/'test.bin'),
                    str(out/'test.o')],check=True,capture_output=True)
    program=(out/'test.bin').read_bytes()
    if len(program)!=0xe000:raise ValueError('Wrong fixture size')
    for address,size,name,_ in REGIONS:
        if program[address-0x2000:address-0x2000+size]!=(out/name).read_bytes():
            raise ValueError('Fixture changed tested helper')
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
    if ram[0x6000:0x600d]!=expected:raise ValueError('Corrupted ABI/interrupt frame')
    deferred=bool(pending and (entry=='camera' or not ordinary) and line>=CUTOFF)
    dispatch=0 if deferred or entry=='camera' and not pending else {'fallback':1,'prepare':2,'camera':3}[entry]
    wanted=bytes((pending if deferred else 0,dispatch))
    matched=ram[0x600d:0x600f]==wanted
    if matched==mutant:raise ValueError('Wrong admission or surviving old-cutoff control')
    return dict(line=line,stack=stack,pending=pending,ordinary=ordinary,entry=entry,bank=bank,
        deferred=deferred,actual=list(ram[0x600d:0x600f]),mutant_rejected=mutant,
        artifacts={str(p):sha(p) for p in (out/'test.sfc',out/'memory.ram',out/'receipt.json')})


def audit(candidate,core,out):
    if out.exists():raise ValueError('Fresh output required')
    meta=json.loads((candidate/'manifest.json').read_text())
    if sha(candidate/'native-cpu.sfc')!=meta['rom_sha256']:raise ValueError('Changed ROM')
    spec=meta['experimental_masked_budget']
    for p,h in spec['sources'].items():
        if sha(Path(p))!=h:raise ValueError('Changed source')
    image=(candidate/'native-cpu.sfc').read_bytes()
    for address,size,name,_ in REGIONS:
        if sha(candidate/name)!=spec['helper_sha256'][name]:raise ValueError('Changed helper')
        for bank in range(1,9):
            if image[bank*65536+address:bank*65536+address+size]!=(candidate/name).read_bytes():
                raise ValueError('Cartridge helper differs')
    matrix=[(line,255,pending,ordinary,entry) for line in (0,119,120,193,240,260)
            for pending in (0,1) for ordinary in (0,1) for entry in ('camera','fallback','prepare')]
    matrix += [(180,stack,1,0,entry) for stack in (*range(12),127,250,251,252,253,254,255)
               for entry in ('camera','fallback','prepare')]
    out.mkdir(parents=True)
    def run(item):
        i,case=item
        return execute(core,candidate,out/f'case-{i:03}',*case,0xc1+i%8)
    with ThreadPoolExecutor(max_workers=6) as pool:cases=list(pool.map(run,enumerate(matrix)))
    mutants=[execute(core,candidate,out/('old-cutoff-'+entry),180,0,1,0,entry,0xc1,True)
             for entry in ('camera','fallback','prepare')]
    paths=[Path(__file__),Path('tools/build_masked_budget_trial.py'),Path('tools/build_inline_pitch_trial.py'),
        Path('snes/retained_producer_guard_test.asm'),Path('snes/wram_clear.inc'),Path('tools/smoke_libretro.py'),
        Path('.deps/cc65/bin/ca65'),Path('.deps/cc65/bin/ld65'),core,candidate/'manifest.json',
        candidate/'native-cpu.sfc',candidate/'native_runtime.lbl',candidate/'retained-guard.lbl',
        candidate/'guard.bin',candidate/'retained-guard.bin']
    report=dict(passed=True,cases=cases,mutants=mutants,sources={str(p):sha(p) for p in paths},
        scope=__doc__,release_ready=False,worst_case_bound_proven=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(cases),mutants=len(mutants))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','core','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
