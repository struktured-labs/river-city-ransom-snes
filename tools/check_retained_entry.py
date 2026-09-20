"""Execute real hardware NMI + production retained dispatch, with explicit audio/body spies."""
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
    boot=symbols(candidate/'native_boot.lbl');meta=json.loads((candidate/'manifest.json').read_text())
    rom=(candidate/'native-cpu.sfc').read_bytes();first=boot['nmi'];last=boot['publish_video']
    (out/'native-nmi.bin').write_bytes(rom[first:last])
    (out/'test.cfg').write_text('MEMORY { ROM: start=$2000,size=$E000,file=%O,fill=yes,fillval=$FF; }\n'
        f'SEGMENTS {{ EARLY: load=ROM,type=ro,start=$5F00; NATIVE: load=ROM,type=ro,start=${first:04X}; '
        'CODE: load=ROM,type=ro,start=$8500; RTI: load=ROM,type=ro,start=$F1D8; '
        'HEADER: load=ROM,type=ro,start=$FFC0; VECTORS: load=ROM,type=ro,start=$FFE0; }\n')
    defs=dict(case,NMI_ENTRY=first,RETURN_TAIL=meta['experimental_queued_vblank']['sites']['return'])
    subprocess.run(['.deps/cc65/bin/ca65',*[v for k,n in defs.items() for v in ('-D',f'{k}={n}')],
        '-I','snes','--bin-include-dir',str(out),'-o',str(out/'test.o'),'snes/retained_entry_test.asm'],
        check=True,capture_output=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C',str(out/'test.cfg'),'-Ln',str(out/'test.lbl'),
        '-o',str(out/'test.bin'),str(out/'test.o')],check=True,capture_output=True)
    code=(out/'test.bin').read_bytes();image=bytearray(0x200000)
    for bank in range(9):
        base=bank*65536;image[base+0x2000:base+65536]=code
        # Production return tail, queue and retained-entry code execute intact.
        for a,b in ((0x2000,0x4000),(0x7200,0x7600)):
            image[base+a:base+b]=rom[(bank or 1)*65536+a:(bank or 1)*65536+b]
    if mutation:
        old,new=map(bytes.fromhex,mutation)
        if len(old)!=len(new):raise ValueError('Different mutation extent')
        for bank in range(1,9):
            at=bank*65536+0x7400;block=image[at:at+512]
            if block.count(old)!=1:raise ValueError('Ambiguous retained-entry mutant')
            p=at+block.index(old);image[p:p+len(old)]=new
    checksum(image);(out/'test.sfc').write_bytes(image)
    run=subprocess.run([sys.executable,'-m','tools.smoke_libretro','--core',str(core),
        '--rom',str(out/'test.sfc'),'--kind','adapter','--frames','120',
        '--ram',str(out/'memory.ram'),'--receipt',str(out/'receipt.json')],
        capture_output=True,text=True,timeout=30)
    (out/'execution.log').write_text(run.stdout+run.stderr);run.check_returncode()
    return (out/'memory.ram').read_bytes()


def expected(case):
    admitted=bool(case['RETAINED'] and not case['DEPTH'] and case['TASK']&0xc0==0xc0
                  and case['EARLY'] and not case['MISMATCH'])
    old=case['OLD_ID'];new=(old+1)&65535
    return dict(admitted=admitted,old=old,new=new,bodies=[old,new] if admitted else [new],
                audio=[old,new],retained_after_first=int(admitted and case['MAIN']),
                first_bodies=1 if admitted and case['MAIN'] else (2 if admitted else 1))


def independent(ram,case):
    if len(ram)!=131072:raise ValueError('Incomplete WRAM')
    wanted=expected(case)
    abi=bytes((0x57,0x3c,case['FLAGS']|0x30,0xa6,0x59,0x34,0x12,0x83,case['STACK']))
    if ram[0x6000:0x6009]!=abi or wanted['retained_after_first'] and ram[0x6020:0x6029]!=abi:
        raise ValueError('Hardware/camera return A/B/P/X/Y/D/DB/SP mismatch')
    count=ram[0x1b90];audio_count=ram[0x1b91]
    bodies=[int.from_bytes(ram[0x6080+i*2:0x6082+i*2],'little') for i in range(count)]
    audio=[int.from_bytes(ram[0x6100+i*2:0x6102+i*2],'little') for i in range(audio_count)]
    if bodies!=wanted['bodies'] or audio!=wanted['audio']:
        raise ValueError('Lost/duplicate/reordered original body or audio event')
    counters=[int.from_bytes(ram[p:p+2],'little') for p in (0x1b88,0x1b8a)]
    target=case['QUEUE_COUNTER']+int(wanted['admitted'])
    if (ram[0x1b87] or ram[0x1b8c] or counters!=[target,target] or
            int.from_bytes(ram[0x1c04:0x1c06],'little')!=wanted['new'] or
            ram[0x1c0a]!=case['DEPTH'] or ram[0x1ce0]):
        raise ValueError('Queue/native/depth ownership mismatch')
    initial=bytes((wanted['retained_after_first'],wanted['new']&255,wanted['new']>>8,
                   wanted['first_bodies'],2))
    if ram[0x6040:0x6045]!=initial:raise ValueError('Incorrect first hardware return state')
    fallback=case['COUNTER']+int(bool(case['RETAINED']))
    served=fallback+int(wanted['retained_after_first'])
    if (int.from_bytes(ram[0x1ce4:0x1ce6],'little')!=served or
            int.from_bytes(ram[0x1ce6:0x1ce8],'little')!=fallback):
        raise ValueError('Retained served/fallback counter mismatch')
    return dict(**wanted,actual_bodies=bodies,actual_audio=audio)


def matrix():
    base=dict(RETAINED=1,MAIN=1,DEPTH=0,TASK=0xc0,EARLY=1,MISMATCH=0,
              OLD_ID=1,COUNTER=0,QUEUE_COUNTER=0,FLAGS=0x35,STACK=255,BANK=0xc7)
    cases=[dict(base,FLAGS=p,STACK=s,BANK=b,OLD_ID=i) for p in (0x35,0xbd)
           for s in (0x20,0x80,0xff) for b in (0xc1,0xc7) for i in (1,255,65535)]
    for change in (dict(RETAINED=0,MAIN=0),dict(MAIN=0),dict(EARLY=0),dict(MISMATCH=-1),
                   dict(DEPTH=2),dict(TASK=0),dict(COUNTER=255),dict(QUEUE_COUNTER=255)):
        cases.append(dict(base,**change))
    return cases


def audit(candidate,core,out):
    if out.exists():raise ValueError('Fresh output required')
    meta=json.loads((candidate/'manifest.json').read_text());sources=dict(meta['experimental_retained_entry']['sources'])
    for p,d in sources.items():
        if sha(Path(p))!=d:raise ValueError('Changed implementation source')
    if sha(candidate/'native-cpu.sfc')!=meta['rom_sha256']:raise ValueError('Changed cartridge')
    out.mkdir(parents=True)
    def run(item):
        i,c=item;folder=out/f'case-{i:03}';ram=execute(candidate,core,folder,c)
        return dict(case=c,result=independent(ram,c),artifacts={str(p):sha(p) for p in folder.iterdir()
                    if p.suffix in ('.sfc','.ram','.lbl','.json')})
    with ThreadPoolExecutor(max_workers=6) as pool:cases=list(pool.map(run,enumerate(matrix())))
    mutants=[]
    for name,change in (('lost-new-event',('ee871b','eaeaea')),
                        ('early-new-identity',('ee881b','ee041c')),
                        ('old-retained-not-cleared',('9ce01c','eaeaea'))):
        folder=out/name;c=matrix()[0];ram=execute(candidate,core,folder,c,change)
        try:independent(ram,c)
        except ValueError as exc:mutants.append(dict(name=name,rejected=True,reason=str(exc)))
        else:raise ValueError('Retained-entry mutant survived')
    paths=[Path(__file__),Path('snes/retained_entry_test.asm'),Path('snes/early_audio_abi.inc'),
        Path('snes/wram_clear.inc'),Path('tools/smoke_libretro.py'),core,candidate/'native-cpu.sfc',candidate/'manifest.json']
    sources.update({str(p):sha(p) for p in paths})
    report=dict(passed=True,cases=cases,mutants=mutants,sources=sources,release_ready=False,
        mutant_artifacts={str(p):sha(p) for m in mutants for p in (out/m['name']).iterdir()
                          if p.suffix in ('.sfc','.ram','.json')},
        scope=__doc__+' Sound log is an independent transport spy with the production suppression '
        'macro; actual SPC waveforms and the game body require separate integration qualification.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(cases),mutants=len(mutants))))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ('candidate','core','out'):parser.add_argument('--'+k,type=Path,required=True)
    audit(**vars(parser.parse_args()))
