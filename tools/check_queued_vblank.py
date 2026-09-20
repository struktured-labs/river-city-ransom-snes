"""Execute actual VBlank collection and production return-tail chaining in Snes9x."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_retained_producer_guard import symbols


def execute(candidate,core,out,case,mutation=None):
    out.mkdir(parents=True)
    meta=json.loads((candidate/'manifest.json').read_text())['experimental_queued_vblank']
    entries=meta['entries']; boot=symbols(candidate/'native_boot.lbl')
    defs=dict(case,COLLECT=entries['collect_vblank'],READ_LONG=entries['ring_read_long'],
        READ_SHORT=entries['ring_read_short'],RETURN_TAIL=meta['sites']['return'],NMI_ENTRY=boot['nmi'])
    first=boot['nmi']
    (out/'test.cfg').write_text(f'MEMORY {{ ROM: start=${first:04X},size=${65536-first:04X},file=%O,fill=yes,fillval=$FF; }}\n'
        'SEGMENTS { NATIVE: load=ROM,type=ro; CODE: load=ROM,type=ro,start=$8500; '
        'HEADER: load=ROM,type=ro,start=$FFC0; VECTORS: load=ROM,type=ro,start=$FFE0; }\n')
    subprocess.run(['.deps/cc65/bin/ca65',*[v for k,n in defs.items() for v in ('-D',f'{k}={n}')],
        '-I','snes','-o',str(out/'test.o'),'snes/queued_vblank_test.asm'],check=True,capture_output=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C',str(out/'test.cfg'),'-Ln',str(out/'test.lbl'),
        '-o',str(out/'test.bin'),str(out/'test.o')],check=True,capture_output=True)
    code=(out/'test.bin').read_bytes(); production=(candidate/'native-cpu.sfc').read_bytes()
    image=bytearray(0x200000)
    for bank in range(9):
        base=bank*65536; source=(bank or 1)*65536
        image[base+0x2000:base+0x8000]=production[source+0x2000:source+0x8000]
        image[base+first:base+65536]=code
    if mutation:
        old,new=map(bytes.fromhex,mutation)
        if len(old)!=len(new):raise ValueError('Mutation length changed')
        for bank in range(1,9):
            at=bank*65536+meta['helper'];body=image[at:at+meta['size']]
            if body.count(old)!=1:raise ValueError('Ambiguous mutant preimage')
            where=at+body.index(old);image[where:where+len(old)]=new
    checksum(image);(out/'test.sfc').write_bytes(image)
    run=subprocess.run([sys.executable,'-m','tools.smoke_libretro','--core',str(core),
        '--rom',str(out/'test.sfc'),'--kind','adapter','--frames','120',
        '--ram',str(out/'memory.ram'),'--receipt',str(out/'receipt.json')],
        capture_output=True,text=True,timeout=30)
    (out/'execution.log').write_text(run.stdout+run.stderr)
    if run.returncode:raise ValueError('Queue fixture execution failed: '+run.stderr[-400:])
    return (out/'memory.ram').read_bytes()


def independent(ram,c):
    if len(ram)!=131072:raise ValueError('Incomplete WRAM')
    accepted=c['EVENTS'] if c['DEPTH']==1 and c['TASK']&0xc0==0xc0 and c['CONTROL']&128 and not c['ACKNOWLEDGED'] else 0
    full=c['PENDING']==255
    count=0 if full else accepted
    wanted_pending=c['PENDING']+count
    before_counter=c['COUNTER']+count
    before=bytes((wanted_pending,1,before_counter&255,before_counter>>8))
    if ram[0x6020:0x6024]!=before:raise ValueError('Collection/active-event identity mismatch')
    value=0xbc if c['READ_KIND'] else 0x57
    flags=(c['FLAGS']|0x80)&~2 if c['READ_KIND'] else c['FLAGS']
    abi=bytes((value,0x3c,flags|0x30,0xa6,0x59,0x34,0x12,0x83,c['STACK']))
    if ram[0x6000:0x6009]!=abi:raise ValueError('Collector/read A/B/P/X/Y/D/DB/SP mismatch')
    if ram[0x1b8c]!=int(full and accepted>0):raise ValueError('Wrong overflow indication')
    if not full:
        services=count+c['PENDING']+c['TAIL_PENDING']
        counters=c['COUNTER']+services
        if (ram[0x1b87]!=0 or int.from_bytes(ram[0x1b88:0x1b8a],'little')!=c['COUNTER']+count+c['TAIL_PENDING'] or
                int.from_bytes(ram[0x1b8a:0x1b8c],'little')!=counters or
                ram[0x1c0a]!=0 or int.from_bytes(ram[0x1c04:0x1c06],'little')!=1+services):
            raise ValueError('Lost/duplicate service or depth/counter error')
        expected=bytes(range(1,services+2))
        if ram[0x1b8e]!=services+1 or ram[0x1b90:0x1b90+len(expected)]!=expected:
            raise ValueError('Wrong completed-body event-ID sequence')
        tail=bytes((0x57,0x3c,c['FLAGS']|0x30,0xa6,0x59,0x34,0x12,0x83,c['STACK']))
        if ram[0x6010:0x6019]!=tail:raise ValueError('Tail-chain caller ABI mismatch')
    return dict(collected=count,tail_collected=c['TAIL_PENDING'],overflow=bool(full and accepted))


def matrix():
    cases=[]
    def add(**changes):
        c=dict(EVENTS=1,ACKNOWLEDGED=0,DEPTH=1,TASK=0xc0,CONTROL=0x80,PENDING=0,COUNTER=0,
               TAIL_PENDING=0,READ_KIND=0,FLAGS=0x35,BANK=0xc7,STACK=0xff)
        c.update(changes);cases.append(c)
    for kind in (0,1,2):
        for events in (0,1,2):
            for flags in (0x35,0xbd):
                for bank in (0xc1,0xc7):
                    for stack in (0x20,0x80,0xff):
                        add(READ_KIND=kind,EVENTS=events,FLAGS=flags,BANK=bank,STACK=stack)
    for kind in (0,1,2):
        for changes in (dict(ACKNOWLEDGED=1),dict(DEPTH=0),dict(DEPTH=2),dict(TASK=0),
                        dict(CONTROL=0),dict(COUNTER=255),dict(EVENTS=0,TAIL_PENDING=1)):
            add(READ_KIND=kind,**changes)
    add(PENDING=255)
    return cases


def audit(candidate,core,out):
    if out.exists():raise ValueError('Fresh output required')
    meta=json.loads((candidate/'manifest.json').read_text())
    sources=dict(meta['experimental_queued_vblank']['sources'])
    for p,d in sources.items():
        if sha(Path(p))!=d:raise ValueError('Changed implementation source')
    if sha(candidate/'native-cpu.sfc')!=meta['rom_sha256']:raise ValueError('Changed cartridge')
    cases=matrix();out.mkdir(parents=True)
    def check(item):
        i,c=item;folder=out/f'case-{i:03}'
        ram=execute(candidate,core,folder,c)
        result=independent(ram,c)
        return dict(case=c,result=result,artifacts={str(p):sha(p) for p in folder.iterdir()
                    if p.suffix in ('.sfc','.ram','.lbl','.json')})
    with ThreadPoolExecutor(max_workers=6) as pool:results=list(pool.map(check,enumerate(cases)))
    mutations=(('lost-pending',('ee871b','eaeaea')),('unacknowledged-duplicate',('ad1042','ad1242')),
               ('early-event-identity',('ee881b','ee041c')),('lost-service-count',('ee8a1b','eaeaea')))
    c=next(c for c in cases if c['EVENTS']==1 and c['READ_KIND']==0)
    mutants=[]
    for name,mutation in mutations:
        ram=execute(candidate,core,out/name,c,mutation)
        try:independent(ram,c)
        except ValueError as exc:mutants.append(dict(name=name,rejected=True,reason=str(exc)))
        else:raise ValueError('Queue mutant survived')
    paths=[Path(__file__),Path('snes/queued_vblank_test.asm'),Path('snes/wram_clear.inc'),
           Path('tools/smoke_libretro.py'),core,candidate/'native-cpu.sfc',candidate/'manifest.json']
    sources.update({str(p):sha(p) for p in paths})
    report=dict(passed=True,cases=results,mutants=mutants,sources=sources,release_ready=False,
        scope=__doc__+' The fixture controls original task bodies and logs service IDs, not actual SPC/audio. '
        'Production collection, load wrappers and return-tail code execute; selected E1 stack/bank cases only.',
        mutant_artifacts={str(p):sha(p) for m in mutants for p in (out/m['name']).iterdir()
                          if p.suffix in ('.sfc','.ram','.lbl','.json')})
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(cases),mutants=len(mutants))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','core','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
