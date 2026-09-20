"""Execute the real deferred beam wait during active display and VBlank."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_retained_producer_guard import symbols


def execute(candidate,core,out,case):
    out.mkdir(parents=True)
    boot=symbols(candidate/'native_boot.lbl');first=boot['@deferred_late_vblank'];last=boot['@deferred_late_vblank_done']
    rom=(candidate/'native-cpu.sfc').read_bytes()
    (out/'wait.bin').write_bytes(rom[first:last])
    (out/'test.cfg').write_text(f'MEMORY {{ ROM: start=${first:04X},size=${65536-first:04X},file=%O,fill=yes,fillval=$FF; }}\n'
        'SEGMENTS { WAIT: load=ROM,type=ro; CODE: load=ROM,type=ro,start=$8500; '
        'HEADER: load=ROM,type=ro,start=$FFC0; VECTORS: load=ROM,type=ro,start=$FFE0; }\n')
    defs=dict(case,WAIT_ENTRY=first)
    subprocess.run(['.deps/cc65/bin/ca65',*[v for k,n in defs.items() for v in ('-D',f'{k}={n}')],
        '-I','snes','--bin-include-dir',str(out),'-o',str(out/'test.o'),'snes/retained_wait_test.asm'],check=True,capture_output=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C',str(out/'test.cfg'),'-o',str(out/'test.bin'),str(out/'test.o')],check=True,capture_output=True)
    code=(out/'test.bin').read_bytes();image=bytearray(0x200000)
    for bank in range(9):
        base=bank*65536;image[base+first:base+65536]=code
        image[base+0x7400:base+0x7600]=rom[(bank or 1)*65536+0x7400:(bank or 1)*65536+0x7600]
    checksum(image);(out/'test.sfc').write_bytes(image)
    run=subprocess.run([sys.executable,'-m','tools.smoke_libretro','--core',str(core),'--rom',str(out/'test.sfc'),
        '--kind','adapter','--frames','120','--ram',str(out/'memory.ram'),'--receipt',str(out/'receipt.json')],
        capture_output=True,text=True,timeout=30)
    (out/'execution.log').write_text(run.stdout+run.stderr);run.check_returncode()
    return (out/'memory.ram').read_bytes()


def independent(ram,case):
    if len(ram)!=131072 or ram[0x6000:0x6006]!=bytes((0xa6,0x59,0x34,0x12,0x83,case['STACK'])):
        raise ValueError('Wait corrupted index, DP, bank or stack')
    returned=int.from_bytes(ram[0x6006:0x6008],'little');line=case['LINE']
    expected=max(line,250) if line>=240 else line
    if not 0<=(returned-expected)%262<=2:
        raise ValueError(f'Deferred wait returned at {returned}, expected near {expected}')
    return dict(start_line=line,return_line=returned)


def audit(candidate,previous,core,out):
    if out.exists():raise ValueError('Fresh output required')
    meta=json.loads((candidate/'manifest.json').read_text());sources=dict(meta['experimental_retained_entry']['sources'])
    if not meta['experimental_retained_entry'].get('active_wait_guard'):raise ValueError('Wrong trial')
    for p,d in sources.items():
        if sha(Path(p))!=d:raise ValueError('Changed implementation')
    out.mkdir(parents=True)
    cases=[dict(LINE=line,FLAGS=flags,BANK=bank,STACK=stack) for line in (0,40,120,239,240,249,250,255,260)
           for flags in (0x35,0xbd) for bank,stack in ((0xc1,0x20),(0xc7,0xff))]
    def run(item):
        i,c=item;folder=out/f'case-{i:03}';ram=execute(candidate,core,folder,c)
        return dict(case=c,result=independent(ram,c),artifacts={str(p):sha(p) for p in folder.iterdir()
                    if p.suffix in ('.sfc','.ram','.json')})
    with ThreadPoolExecutor(max_workers=6) as pool:results=list(pool.map(run,enumerate(cases)))
    c=dict(LINE=40,FLAGS=0x35,BANK=0xc7,STACK=255)
    old=execute(previous,core,out/'old-wait',c)
    try:independent(old,c)
    except ValueError as exc:negative=dict(rejected=True,reason=str(exc))
    else:raise ValueError('Old active-scanline wait passed')
    paths=[Path(__file__),Path('snes/retained_wait_test.asm'),Path('tools/smoke_libretro.py'),Path('snes/wram_clear.inc'),
        core,candidate/'native-cpu.sfc',candidate/'manifest.json',previous/'native-cpu.sfc',previous/'native_boot.lbl']
    sources.update({str(p):sha(p) for p in paths})
    report=dict(passed=True,cases=results,old_wait=negative,sources=sources,release_ready=False,
        artifacts={str(p.relative_to(out)):sha(p) for p in (out/'old-wait').iterdir() if p.suffix in ('.sfc','.ram','.json')},
        scope=__doc__+' Actual beam reads and production wait/helper bytes; continuation is an ABI/beam recorder.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(cases),old_wait=negative)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ('candidate','previous','core','out'):parser.add_argument('--'+k,type=Path,required=True)
    audit(**vars(parser.parse_args()))
