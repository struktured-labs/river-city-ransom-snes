"""Actual dispatcher ABI/full-WRAM comparisons and independent common-register oracle."""
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
    defs = dict(ENTRY=symbols(candidate/'native_runtime.lbl')['dispatch_write'],**case)
    (out/'test.cfg').write_text('MEMORY { ROM: start=$8500,size=$7B00,file=%O,fill=yes,fillval=$FF; }\n'
        'SEGMENTS { CODE: load=ROM,type=ro; HEADER: load=ROM,type=ro,start=$FFC0; '
        'VECTORS: load=ROM,type=ro,start=$FFE0; }\n')
    subprocess.run(['.deps/cc65/bin/ca65',*[v for k,n in defs.items() for v in ('-D',f'{k}={n}')],
        '-I','snes','-o',str(out/'test.o'),'snes/ppu_register_test.asm'],check=True,capture_output=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C',str(out/'test.cfg'),'-o',str(out/'test.bin'),
                    str(out/'test.o')],check=True,capture_output=True)
    program = (out/'test.bin').read_bytes()
    production = (candidate/'native-cpu.sfc').read_bytes()
    image = bytearray(0x200000)
    # Each selected bank keeps its OWN production runtime, not a bank1 copy.
    for bank in range(9):
        source = (bank or 1)*65536
        image[bank*65536+0x2000:bank*65536+0x8000] = production[source+0x2000:source+0x8000]
        image[bank*65536+0x8500:(bank+1)*65536] = program
    if mutation:
        needle,replacement = map(bytes.fromhex,mutation)
        if len(needle) != len(replacement):
            raise ValueError('Mutation size changed')
        for bank in range(1,9):
            start = bank*65536+HELPER
            body = image[start:start+SIZE]
            if body.count(needle) != 1:
                raise ValueError('Ambiguous mutation')
            at = start+body.index(needle)
            image[at:at+len(needle)] = replacement
    checksum(image)
    (out/'test.sfc').write_bytes(image)
    run = subprocess.run([sys.executable,'-m','tools.smoke_libretro','--core',str(core),
        '--rom',str(out/'test.sfc'),'--kind','adapter','--frames','120','--ram',str(out/'memory.ram'),
        '--receipt',str(out/'receipt.json')],capture_output=True,text=True,timeout=30)
    (out/'execution.log').write_text(run.stdout+run.stderr)
    if run.returncode:
        raise ValueError('Fixture failed: '+run.stderr[-500:])
    return (out/'memory.ram').read_bytes()


def independent(ram,case):
    address,value = case['ADDRESS'],case['VALUE']
    register = address&7
    if address>>8 != 0x20 or register not in (0,3,5,6):
        return False
    expected = bytearray(b'\x5a'*0x300)
    def put(address,value):
        expected[address-0x1b00] = value
    for address,value0 in ((0x1b20,address&255),(0x1b21,address>>8),(0x1b22,value),
        (0x1c20,case['OLD_CTRL']),(0x1c25,case['LATCH']),(0x1c27,0x20),(0x1c26,0x1f),
        (0x1c18,0),(0x1c06,0),(0x1c60,1),(0x1c61,0),(0x1c0a,1)):
        put(address,value0)
    if register==0:
        if (case['OLD_CTRL']^value)&24:
            put(0x1cbb,1)
        put(0x1c20,value)
    elif register==3:
        put(0x1c23,value)
    elif register==5:
        put(0x1c28+case['LATCH'],value)
        put(0x1c25,case['LATCH']^1)
    elif case['LATCH']:
        put(0x1c26,value);put(0x1c25,0)
    else:
        put(0x1c27,value&63);put(0x1c25,1)
    actual = bytearray(ram[0x1b00:0x1e00])
    # Fixture heartbeat belongs to the runner, not the dispatcher.
    for offset in (0x162,0x163):
        actual[offset] = expected[offset]
    if actual != expected:
        raise ValueError('Independent register/scratch/dirty mismatch')
    # LDX/LDY/LDA at fixture entry set NZ according to A=$57; other P bits
    # survive. E=1 forces M/X bits and PHP exposes both as1.
    flags = (case['FLAGS']|0x30)&~0x82
    abi = bytes((0x57,0x1b,flags,0xa6,0x59,0x34,0x12,0x83,case['STACK']))
    if ram[0x6000:0x6009] != abi:
        raise ValueError('Independent A/B/P/X/Y/D/DB/SP mismatch')
    return True


def audit(parent,candidate,core,out):
    if out.exists():
        raise ValueError('Fresh output required')
    meta = json.loads((candidate/'manifest.json').read_text())
    sources = dict(meta['experimental_ppu_register_fast']['sources'])
    for name,digest in sources.items():
        if sha(Path(name)) != digest:
            raise ValueError('Changed implementation source')
    for root in (parent,candidate):
        if sha(root/'native-cpu.sfc') != json.loads((root/'manifest.json').read_text())['rom_sha256']:
            raise ValueError('Changed cartridge')
    values = (0,1,7,8,15,16,23,24,31,32,63,64,127,128,254,255)
    cases = []
    for register in (0,3,5,6):
        for latch in (0,1,7):
            for value in values:
                cases.append(dict(ADDRESS=0x2000+register,VALUE=value,LATCH=latch,
                    OLD_CTRL=(value*37^0x5a)&255,FLAGS=(value^0xc5)|0x30,
                    BANK=0xc1+len(cases)%8,STACK=(9,0x18,0x40,0x80,0xfc,0xff)[len(cases)%6]))
    for address in (0x2008,0x20fe,0x2002,0x2004,0x2007,0x4018,0x8000,0xa001,0xc000,0xe001):
        for value in (0,0x18,0xff):
            cases.append(dict(ADDRESS=address,VALUE=value,LATCH=1,OLD_CTRL=0,FLAGS=0x75,BANK=0xc8,STACK=0xff))
    out.mkdir(parents=True)
    def check(item):
        i,case = item
        folder = out/f'case-{i:03}'
        old = execute(parent,core,folder/'before',case)
        new = execute(candidate,core,folder/'after',case)
        if len(old)!=131072 or len(new)!=131072:
            raise ValueError('Incomplete WRAM')
        excluded = set(range(0x100,0x200)) | {0x1c62,0x1c63}
        mismatch = [i for i,(a,b) in enumerate(zip(old,new)) if a!=b and i not in excluded]
        if mismatch:
            raise ValueError('Full RAM mismatch '+str((case,mismatch[:20])))
        checked = independent(new,case)
        return dict(case=case,independent_oracle=checked,artifacts={str(p):sha(p)
            for p in folder.rglob('*') if p.suffix in ('.sfc','.ram','.json')})
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(check,enumerate(cases)))
    mutants = []
    for name,case,mutation in (
        ('wrong-high-mask',dict(cases[0],ADDRESS=0x2006,VALUE=0xff,LATCH=0),('293f','297f')),
        ('lost-chr-dirty',dict(cases[0],OLD_CTRL=0,VALUE=0x18),('8dbb1c','eaeaea')),
        ('wrong-scroll-toggle',dict(cases[0],ADDRESS=0x2005,LATCH=1),('4901','4900')),
        ('lost-hidden-b',cases[0],('a91beb','a91bea'))):
        ram = execute(candidate,core,out/name,case,mutation)
        try:
            independent(ram,case)
        except ValueError as exc:
            mutants.append(dict(name=name,rejected=True,reason=str(exc)))
        else:
            raise ValueError('Mutant survived: '+name)
    paths = [Path(__file__),Path('snes/ppu_register_test.asm'),Path('snes/wram_clear.inc'),
             Path('tools/smoke_libretro.py'),core,*[root/name for root in (parent,candidate)
             for name in ('native-cpu.sfc','manifest.json','native_runtime.lbl')]]
    sources.update({str(p):sha(p) for p in paths})
    report = dict(passed=True,cases=results,mutants=mutants,sources=sources,release_ready=False,
        scope=__doc__+' Only dead stack/heartbeat excluded. NMI ownership is preset; not injected-NMI timing proof. '
        'Long-call stack extent stays inside page1. Historical SP0..2 baseline fails to return and SP7..8 '
        'corrupts legacy DP; those separately retained exploratory fixtures are not passing ABI cases.',
        mutant_artifacts={str(p):sha(p) for name in [m['name'] for m in mutants] for p in (out/name).iterdir()
                          if p.suffix in ('.sfc','.ram','.json')})
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(results),
                         independent=sum(r['independent_oracle'] for r in results),mutants=len(mutants))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent','candidate','core','out'):
        p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
