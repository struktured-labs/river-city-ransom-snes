"""Execute queue-priority admission with actual guard bytes and wrapped E1 stacks."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_retained_producer_guard import symbols


def execute(candidate,core,out,c,mutant=False):
    out.mkdir(parents=True)
    labels=symbols(candidate/'native_runtime.lbl');entries=symbols(candidate/'retained-guard.lbl')
    helper=(candidate/'queued-vblank.bin').read_bytes()
    if mutant:
        at=symbols(candidate/'queued-vblank.lbl')['queued_producer_guard']-0x7200
        if helper[at:at+7]!=bytes.fromhex('ad871bf0023860'):raise ValueError('Wrong priority preimage')
        helper=helper[:at+3]+b'\xd0'+helper[at+4:]
    (out/'queued-vblank.bin').write_bytes(helper)
    (out/'retained-guard.bin').write_bytes((candidate/'retained-guard.bin').read_bytes())
    source=Path('snes/retained_producer_guard_test.asm').read_text()
    marker='    clear_wram_dma\n'
    if source.count(marker)!=1:raise ValueError('Changed fixture reset')
    source=source.replace(marker,marker+'    lda #QUEUED\n    sta a:$1B87\n')
    source+='\n.segment "QUEUE"\n    .incbin "queued-vblank.bin"\n'
    (out/'test.asm').write_text(source)
    (out/'test.cfg').write_text('MEMORY { ROM: start=$2000,size=$E000,file=%O,fill=yes,fillval=$FF; }\n'
        f'SEGMENTS {{ PREPARE: load=ROM,type=ro,start=${labels["second_tick_prepare"]:04x}; '
        f'FALLBACK: load=ROM,type=ro,start=${labels["second_tick_prepare_fallback"]:04x}; '
        'QUEUE: load=ROM,type=ro,start=$7200; GUARD: load=ROM,type=ro,start=$7B00; '
        'CODE: load=ROM,type=ro,start=$8500; HEADER: load=ROM,type=ro,start=$FFC0; '
        'VECTORS: load=ROM,type=ro,start=$FFE0; }\n')
    defs=dict(TARGET_LINE=c['line'],STACK=c['stack'],PENDING=c['pending'],ORDINARY=c['ordinary'],
        QUEUED=c['queued'],CAMERA_RETURN=labels['camera_deferred_nmi_return'],BANK=c['bank'],
        GUARD_ENTRY=entries['guarded_'+c['entry']])
    subprocess.run(['.deps/cc65/bin/ca65',*[v for k,n in defs.items() for v in ('-D',f'{k}={n}')],
        '-I','snes','--bin-include-dir',str(out),'-o',str(out/'test.o'),str(out/'test.asm')],
        check=True,capture_output=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C',str(out/'test.cfg'),'-o',str(out/'test.bin'),
        str(out/'test.o')],check=True,capture_output=True)
    program=(out/'test.bin').read_bytes()
    for at,data in ((0x7200,helper),(0x7b00,(out/'retained-guard.bin').read_bytes())):
        if program[at-0x2000:at-0x2000+len(data)]!=data:raise ValueError('Relocated helper')
    image=bytearray(0x200000)
    for bank in range(9):image[bank*65536+0x2000:(bank+1)*65536]=program
    checksum(image);(out/'test.sfc').write_bytes(image)
    run=subprocess.run([sys.executable,'-m','tools.smoke_libretro','--core',str(core),
        '--rom',str(out/'test.sfc'),'--kind','adapter','--frames','120',
        '--ram',str(out/'memory.ram'),'--receipt',str(out/'receipt.json')],
        capture_output=True,text=True,timeout=30)
    (out/'execution.log').write_text(run.stdout+run.stderr);run.check_returncode()
    ram=(out/'memory.ram').read_bytes();ret=labels['camera_deferred_nmi_return']+c['ordinary']
    expected=bytes((0x56,0x78,(c['stack']-6)&255,0x34,0x12,0x82,0x78,0x56,0x40,0x35,
                    ret&255,ret>>8,c['stack']))
    if ram[0x6000:0x600d]!=expected or ram[0x1b87]!=c['queued']:
        raise ValueError('Changed ABI, interrupt frame, or event ownership')
    deferred=bool(c['pending'] and not c['ordinary'] and (c['queued'] or c['line']>=120))
    wanted=bytes((c['pending'] if deferred else 0,0 if deferred else (1 if c['entry']=='fallback' else 2)))
    matched=ram[0x600d:0x600f]==wanted
    if matched==mutant:raise ValueError('Wrong priority or surviving mutant')
    return dict(case=c,deferred=deferred,actual=list(ram[0x600d:0x600f]),mutant_rejected=mutant,
        artifacts={str(p):sha(p) for p in out.iterdir() if p.suffix in ('.sfc','.ram','.json')})


def audit(candidate,core,out):
    if out.exists():raise ValueError('Fresh output required')
    meta=json.loads((candidate/'manifest.json').read_text());spec=meta['experimental_queued_vblank']
    if not spec.get('defer_pending') or sha(candidate/'native-cpu.sfc')!=meta['rom_sha256']:
        raise ValueError('Wrong candidate')
    for p,d in spec['sources'].items():
        if sha(Path(p))!=d:raise ValueError('Changed implementation source')
    image=(candidate/'native-cpu.sfc').read_bytes()
    for at,name in ((0x7200,'queued-vblank.bin'),(0x7b00,'retained-guard.bin')):
        data=(candidate/name).read_bytes()
        for bank in range(1,9):
            if image[bank*65536+at:bank*65536+at+len(data)]!=data:raise ValueError('Wrong actual helper')
    cases=[dict(line=line,stack=255,pending=pending,ordinary=ordinary,queued=queued,entry=entry)
           for line in (0,40,119,120,240) for pending in (0,1) for ordinary in (0,1)
           for queued in (0,1) for entry in ('fallback','prepare')]
    cases += [dict(line=40,stack=stack,pending=1,ordinary=0,queued=1,entry=entry)
              for stack in range(12) for entry in ('fallback','prepare')]
    for i,c in enumerate(cases):c['bank']=0xc1+i%8
    out.mkdir(parents=True)
    def run(item):
        i,c=item;return execute(candidate,core,out/f'case-{i:03}',c)
    with ThreadPoolExecutor(max_workers=6) as pool:results=list(pool.map(run,enumerate(cases)))
    mutants=[execute(candidate,core,out/('ignored-'+entry),
        dict(line=40,stack=255,pending=1,ordinary=0,queued=1,entry=entry,bank=0xc7),True)
        for entry in ('fallback','prepare')]
    files=[Path(__file__),Path('snes/retained_producer_guard_test.asm'),Path('snes/wram_clear.inc'),
        Path('tools/smoke_libretro.py'),core,candidate/'manifest.json',candidate/'native-cpu.sfc']
    sources=dict(spec['sources']);sources.update({str(p):sha(p) for p in files})
    report=dict(passed=True,cases=results,mutants=mutants,sources=sources,release_ready=False,
        scope=__doc__+' Producers are dispatch spies; original preparation and audio execute only in integration tests.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(cases),mutants=len(mutants))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','core','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
