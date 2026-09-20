"""Differential actual-cartridge ring routines plus independent CIRAM/dirty oracle."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_retained_producer_guard import symbols
from tools.build_ring_stride_trial import HELPER


def execute(candidate,core,out,case,mutant=False):
    out.mkdir(parents=True,exist_ok=False)
    entry=symbols(candidate/'native_runtime.lbl')['bulk_ring_bytes']
    defs=dict(ENTRY=entry,**case)
    (out/'test.cfg').write_text('MEMORY { ROM: start=$8500,size=$7B00,file=%O,fill=yes,fillval=$FF; }\n'
        'SEGMENTS { CODE: load=ROM,type=ro; HEADER: load=ROM,type=ro,start=$FFC0; '
        'VECTORS: load=ROM,type=ro,start=$FFE0; }\n')
    subprocess.run(['.deps/cc65/bin/ca65',*[v for k,n in defs.items() for v in ('-D',f'{k}={n}')],
        '-I','snes','-o',str(out/'test.o'),'snes/ring_stride_test.asm'],check=True,capture_output=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C',str(out/'test.cfg'),'-o',str(out/'test.bin'),
                    str(out/'test.o')],check=True,capture_output=True)
    program=(out/'test.bin').read_bytes();production=(candidate/'native-cpu.sfc').read_bytes()
    image=bytearray(0x200000)
    for bank in range(9):
        # Keep actual runtime/helper bytes at their real addresses; no relink.
        image[bank*65536+0x2000:bank*65536+0x8000]=production[65536+0x2000:65536+0x8000]
        image[bank*65536+0x8500:(bank+1)*65536]=program
    if mutant:
        needle=bytes.fromhex('69208d261c')
        for bank in range(1,9):
            start=bank*65536+HELPER;helper=image[start:start+256]
            if helper.count(needle)!=1:raise ValueError('Wrong stride mutation preimage')
            image[start+helper.index(needle)+1]=1
    checksum(image);(out/'test.sfc').write_bytes(image)
    run=subprocess.run([sys.executable,'-m','tools.smoke_libretro','--core',str(core),'--rom',str(out/'test.sfc'),
        '--kind','adapter','--frames','120','--ram',str(out/'memory.ram'),'--receipt',str(out/'receipt.json')],
        check=True,capture_output=True,text=True,timeout=30)
    (out/'execution.log').write_text(run.stdout+run.stderr)
    return (out/'memory.ram').read_bytes()


def independent(ram,case):
    # Binary nametable writes only. Decimal/CHR/palette are differential controls.
    if case['FLAGS']&8 or not 0x2000<=case['PPUADDR']<=0x3aff or not 1<=case['COUNT']<=32:
        return False
    shadow=bytearray(65536);dirty=bytearray(i&3 for i in range(128));changed=False
    address=case['PPUADDR'];index=case['RINGINDEX'];stride=32 if case['STRIDE']&4 else 1
    for _ in range(case['COUNT']):
        low=address&255;high=(address>>8)&63
        physical_high=((high&3)|0x20|((high>>1)&4)) if case['MIRROR'] else high&0x27
        physical=physical_high*256+low
        value=0 if case['UNCHANGED'] else index^0xa5
        if shadow[physical]!=value:
            shadow[physical]=value;changed=True
            if high&3==3 and low>=0xc0:
                row=((high&12)<<3)|((low&56)>>1);rows=range(row,row+4)
            else:rows=[((high&15)<<3)|(low>>5)]
            for row in rows:
                dirty[row]|=1;dirty[row^(32 if case['MIRROR'] else 64)]|=1
        address+=stride;index=(index+1)&63
    if (ram[65536:]!=shadow or ram[0x1d00:0x1d80]!=dirty or
            int.from_bytes(ram[0x1c26:0x1c28],'little')!=address or
            ram[0x1c09]!=(0xfc+case['COUNT'])&255 or ram[0x1c85]!=int(changed) or
            ram[0x6000]!=index or ram[0x6003:0x6009]!=bytes((index,0,0x34,0x12,0x82,0xff))):
        raise ValueError('Independent CIRAM/dirty/count/ABI mismatch')
    return True


def audit(parent,candidate,core,out):
    if out.exists():raise ValueError('Fresh output required')
    for folder in (parent,candidate):
        meta=json.loads((folder/'manifest.json').read_text())
        if sha(folder/'native-cpu.sfc')!=meta['rom_sha256']:raise ValueError('Changed cartridge')
    for p,h in meta['experimental_ring_stride_cache']['sources'].items():
        if sha(Path(p))!=h:raise ValueError('Changed helper source')
    out.mkdir(parents=True)
    cases=[]
    for high in (0x20,0x23,0x24,0x27,0x2f,0x30,0x3a):
        for low in (0,0x1f,0xc0,0xf0,0xff):
            for mirror in (0,1):
                cases.append(dict(PPUADDR=high*256+low,COUNT=20,RINGINDEX=60,MIRROR=mirror,
                                  STRIDE=4,UNCHANGED=0,FLAGS=0x75,BANK=0xc1+len(cases)%8))
    for count in (0,1,2,7,8,9,32,33,63):
        for index in (0,31,63):
            cases.append(dict(PPUADDR=0x23ef,COUNT=count,RINGINDEX=index,MIRROR=index&1,
                              STRIDE=4,UNCHANGED=count&1,FLAGS=0x35,BANK=0xc1+len(cases)%8))
    for address in (0x1ff0,0x3bf0,0x3ef0,0x3f00,0x3fff):
        for mode in (0,4):
            cases.append(dict(PPUADDR=address,COUNT=20,RINGINDEX=60,MIRROR=1,STRIDE=mode,
                              UNCHANGED=0,FLAGS=0x35,BANK=0xc1))
    for flags in (0x35,0x75,0x3d,0x7d):
        cases.append(dict(PPUADDR=0x23f0,COUNT=20,RINGINDEX=60,MIRROR=0,STRIDE=4,
                          UNCHANGED=0,FLAGS=flags,BANK=0xc8))
    def check(item):
        i,case=item;folder=out/f'case-{i:03}'
        old=execute(parent,core,folder/'before',case);new=execute(candidate,core,folder/'after',case)
        if len(old)!=131072 or len(new)!=131072:raise ValueError('Incomplete WRAM')
        # Only dead call-stack bytes and the free-running fixture heartbeat
        # are excluded. All original RAM, DP scratch, PPU shadow and dirty
        # state, saved ABI outputs, controller state and counters must match.
        excluded=set(range(0x100,0x200))|{0x1c62,0x1c63}
        mismatch=[n for n,(a,b) in enumerate(zip(old,new)) if a!=b and n not in excluded]
        if mismatch:raise ValueError('Parent/candidate RAM mismatch '+str((i,mismatch[:20])))
        checked=independent(new,case)
        return dict(case=case,independent_oracle=checked,artifacts={str(p):sha(p) for p in folder.rglob('*') if p.suffix in ('.sfc','.ram','.json')})
    with ThreadPoolExecutor(max_workers=6) as pool:results=list(pool.map(check,enumerate(cases)))
    mutant=execute(candidate,core,out/'wrong-stride',cases[0],True)
    try:independent(mutant,cases[0])
    except ValueError:rejected=True
    else:raise ValueError('Wrong stride control survived')
    paths=[Path(__file__),Path('snes/ring_stride_test.asm'),Path('snes/wram_clear.inc'),
        Path('tools/build_ring_stride_trial.py'),Path('tools/smoke_libretro.py'),Path('tools/build_inline_pitch_trial.py'),
        Path('snes/ring_stride_cache.asm'),Path('snes/ring_stride_cache.cfg'),core,
        *[folder/name for folder in (parent,candidate) for name in ('manifest.json','native-cpu.sfc','native_runtime.lbl')],
        candidate/'ring-stride.bin',Path('.deps/cc65/bin/ca65'),Path('.deps/cc65/bin/ld65')]
    report=dict(passed=True,cases=results,mutant_rejected=rejected,
        mutant_artifacts={str(p):sha(p) for p in (out/'wrong-stride').iterdir() if p.suffix in ('.sfc','.ram','.json')},
        sources={str(p):sha(p) for p in paths},scope=__doc__,release_ready=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(results),independent=sum(r['independent_oracle'] for r in results))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','candidate','core','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
