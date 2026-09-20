"""Execute actual post-DMA helper, row advancement and deadline bytes at controlled beam positions."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_retained_producer_guard import symbols


def verify(ram,c,negative=False):
    cursor=(c['cursor']+c['rows'])%128
    expected=cursor.to_bytes(2,'little')+bytes.fromhex('3412001eff1f')
    if ram[0x6000:0x6008]!=expected or ram[0x6008]&0x30 or ram[0x6009]:
        raise ValueError('Wrong cursor or X/Y/DP/SP/DB/width state')
    if ram[0x1d00]!=3 or ram[0x1d7f]!=3 or any(ram[0x1b87:0x1b8d]):
        raise ValueError('Changed unconsumed row ownership or queue')
    continuing=c['transition']!=0 or 240<=c['line']<246
    actual=int.from_bytes(ram[0x6010:0x6012],'little')
    matched=actual==(1 if continuing else 2)
    if matched==negative:raise ValueError('Wrong deadline or surviving mutant')
    return dict(continuing=continuing,actual=actual,cursor=cursor,negative_rejected=negative)


def execute(candidate,core,out,c,negative=False):
    out.mkdir(parents=True)
    b=symbols(candidate/'native_boot.lbl');h=symbols(candidate/'publisher-postdma.lbl')
    defs=dict(TARGET_LINE=c['line'],TRANSITION=c['transition'],CURSOR=c['cursor'],ROWS=c['rows'],
        HELPER=h['postdma_deadline'],BANK=c['bank'])
    # Endpoints are deliberately relocated spies; the production helper's
    # endpoint operands alone are retargeted, never its timing/admission code.
    image=(candidate/'native-cpu.sfc').read_bytes();helper=bytearray((candidate/'publisher-postdma.bin').read_bytes())
    for old,new in ((b['@finish'],0xe100),(b['@next_row'],0xe000)):
        needle=b'\x4c'+old.to_bytes(2,'little')
        if helper.count(needle)!=1:raise ValueError('Wrong endpoint branch')
        helper=helper.replace(needle,b'\x4c'+new.to_bytes(2,'little'))
    if negative:
        at=helper.index(bytes.fromhex('b0'))
        helper[at]=0x80 # Always continue scanning, including late cases.
    (out/'test.cfg').write_text('MEMORY { ROM: start=$E000,size=$2000,file=%O,fill=yes,fillval=$FF; }\n'
        'SEGMENTS { NEXT: load=ROM,type=ro,start=$E000; FINISH: load=ROM,type=ro,start=$E100; '
        'CODE: load=ROM,type=ro,start=$F000; HEADER: load=ROM,type=ro,start=$FFC0; '
        'VECTORS: load=ROM,type=ro,start=$FFE0; }\n')
    subprocess.run(['.deps/cc65/bin/ca65',*[v for k,n in defs.items() for v in ('-D',f'{k}={n}')],
        '-I','snes','-o',str(out/'test.o'),'snes/publisher_postdma_test.asm'],check=True,capture_output=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C',str(out/'test.cfg'),'-o',str(out/'test.bin'),
        str(out/'test.o')],check=True,capture_output=True)
    rom=bytearray(image);rom[0xe000:0x10000]=(out/'test.bin').read_bytes();rom[0x7300:0x7400]=helper
    for start,end in ((b['row_room'],b['row_room']+35),(b['advance_ready_rows'],b['advance_ready_rows']+24)):
        if rom[start:end]!=image[start:end]:raise ValueError('Changed production helper')
    checksum(rom);(out/'test.sfc').write_bytes(rom)
    run=subprocess.run([sys.executable,'-m','tools.smoke_libretro','--core',str(core),
        '--rom',str(out/'test.sfc'),'--kind','adapter','--frames','120',
        '--ram',str(out/'memory.ram'),'--receipt',str(out/'receipt.json')],
        capture_output=True,text=True,timeout=30)
    (out/'execution.log').write_text(run.stdout+run.stderr);run.check_returncode()
    result=verify((out/'memory.ram').read_bytes(),c,negative)
    return dict(case=c,**result,artifacts={str(p):sha(p) for p in out.iterdir() if p.suffix in ('.sfc','.ram','.json')})


def audit(candidate,core,out):
    if out.exists():raise ValueError('Fresh output required')
    meta=json.loads((candidate/'manifest.json').read_text());spec=meta['experimental_publisher_postdma_deadline']
    if sha(candidate/'native-cpu.sfc')!=meta['rom_sha256']:raise ValueError('Changed candidate')
    boot=symbols(candidate/'native_boot.lbl');image=(candidate/'native-cpu.sfc').read_bytes()
    fast=b'\x22'+boot['fast_video_entry'].to_bytes(2,'little')+b'\xc0'
    if fast not in image[boot['publish_video']:boot['fast_video_entry']]:
        raise ValueError('Low-ROM helper requires the actual C0 publisher bridge')
    sources=dict(spec['sources'])
    for p,d in sources.items():
        if sha(Path(p))!=d:raise ValueError('Changed source')
    cases=[dict(line=line,transition=transition,cursor=cursor,rows=rows,bank=bank)
        for line in (0,40,240,244,246,249,255,260) for transition in (0,2)
        for cursor,rows in ((0,1),(63,2),(126,2),(127,1)) for bank in (0x40,0xc0)]
    out.mkdir(parents=True)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results=list(pool.map(lambda item:execute(candidate,core,out/f'case-{item[0]:03}',item[1]),enumerate(cases)))
    negatives=[execute(candidate,core,out/'ignored-deadline',
        dict(line=249,transition=0,cursor=126,rows=2,bank=0xc0),True)]
    for p in (Path(__file__),Path('snes/publisher_postdma_test.asm'),Path('snes/wram_clear.inc'),
        Path('tools/smoke_libretro.py'),candidate/'manifest.json',candidate/'native-cpu.sfc',core):sources[str(p)]=sha(p)
    report=dict(passed=True,cases=results,negative_controls=negatives,sources=sources,release_ready=False,
        scope=__doc__+' Continuation endpoints are spies. Actual DMA and pictures need integration proof.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(cases),negative_controls=len(negatives))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('candidate','core','out'):p.add_argument('--'+k,type=Path,required=True)
    audit(**vars(p.parse_args()))
