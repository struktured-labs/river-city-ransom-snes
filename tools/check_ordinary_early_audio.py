"""Execute ordinary-audio dispatch with the existing real-NMI ownership/ABI fixture."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_retained_producer_guard import symbols
from tools.check_retained_entry import independent, matrix


def execute(candidate, core, out, case, mutant=False):
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
        for a,b in ((0x2000,0x4000),(0x7200,0x7800)):
            image[base+a:base+b]=rom[(bank or 1)*65536+a:(bank or 1)*65536+b]
        if mutant:
            block=image[base+0x7600:base+0x7800];needle=bytes.fromhex('adff1ccd051cf0')
            if block.count(needle)!=1:raise ValueError('Nonunique suppression mutation')
            at=base+0x7600+block.index(needle)+6;image[at:at+2]=b'\xea\xea'
    checksum(image);(out/'test.sfc').write_bytes(image)
    run=subprocess.run([sys.executable,'-m','tools.smoke_libretro','--core',str(core),
        '--rom',str(out/'test.sfc'),'--kind','adapter','--frames','120',
        '--ram',str(out/'memory.ram'),'--receipt',str(out/'receipt.json')],
        capture_output=True,text=True,timeout=30)
    (out/'execution.log').write_text(run.stdout+run.stderr);run.check_returncode()
    return (out/'memory.ram').read_bytes()


def audit(candidate,core,out):
    if out.exists():raise ValueError('Fresh output required')
    meta=json.loads((candidate/'manifest.json').read_text())
    sources=dict(meta['experimental_ordinary_early_audio']['sources'])
    for p,d in sources.items():
        if sha(Path(p))!=d:raise ValueError('Changed implementation source')
    if sha(candidate/'native-cpu.sfc')!=meta['rom_sha256']:raise ValueError('Changed cartridge')
    out.mkdir(parents=True)
    def run(item):
        i,c=item;folder=out/f'case-{i:03}';ram=execute(candidate,core,folder,c)
        return dict(case=c,result=independent(ram,c),artifacts={str(p):sha(p) for p in folder.iterdir()
                    if p.suffix in ('.sfc','.ram','.lbl','.json')})
    with ThreadPoolExecutor(max_workers=4) as pool:cases=list(pool.map(run,enumerate(matrix())))
    c=matrix()[0];folder=out/'duplicate-old-audio';ram=execute(candidate,core,folder,c,True)
    try:independent(ram,c)
    except ValueError as exc:negative=dict(rejected=True,reason=str(exc))
    else:raise ValueError('Duplicate old audio mutation survived')
    paths=[Path(__file__),Path('tools/check_retained_entry.py'),Path('snes/retained_entry_test.asm'),
        Path('snes/early_audio_abi.inc'),Path('snes/wram_clear.inc'),Path('tools/smoke_libretro.py'),
        core,candidate/'native-cpu.sfc',candidate/'manifest.json']
    sources.update({str(p):sha(p) for p in paths})
    report=dict(passed=True,cases=cases,duplicate_old_audio=negative,sources=sources,release_ready=False,
        mutant_artifacts={str(p):sha(p) for p in folder.iterdir() if p.suffix in ('.sfc','.ram','.json')},
        scope=__doc__+' Original body and transport are spies. New actual dispatch and existing '
        'queue/retained-entry/return code execute. Verifies no lost/duplicate event and interrupt ABI; '
        'not actual sound synthesis, gameplay cadence or menu-input ordering.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(cases),negative=negative)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ('candidate','core','out'):parser.add_argument('--'+k,type=Path,required=True)
    audit(**vars(parser.parse_args()))
