"""Execute production camera publication with real nine-bit beam registers."""
import argparse
import json
from pathlib import Path
import subprocess

from tools.benchmark_report import sha
from tools.check_oam_live_half import checksum


def case(core, out, line, nops=0, mutation=None, line30=True):
    out.mkdir(parents=True, exist_ok=False)
    helper = Path('snes/camera_publish_safe.inc').read_text()
    if mutation:
        before, after = mutation
        if helper.count(before) != 1:
            raise ValueError('Ambiguous camera mutation')
        helper = helper.replace(before, after)
    (out/'camera_publish_safe.inc').write_text(helper)
    # Source beside the disposable helper ensures the mutation is selected.
    (out/'test.asm').write_bytes(Path('snes/camera_publish_test.asm').read_bytes())
    defines = ['-D','EXPERIMENTAL_CAMERA_LINE30=1'] if line30 else []
    subprocess.run(['.deps/cc65/bin/ca65', *defines, '-D',f'TARGET_LINE={line}', '-D',f'DELAY_NOPS={nops}',
        '-I','snes','-o',str(out/'test.o'),str(out/'test.asm')], check=True, capture_output=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/native_boot.cfg','-o',str(out/'test.bin'),
                    str(out/'test.o')], check=True, capture_output=True)
    image = bytearray(2*1024*1024)
    image[0x8000:0x10000] = (out/'test.bin').read_bytes()
    (out/'test.sfc').write_bytes(checksum(image))
    run = subprocess.run(['python3','tools/smoke_libretro.py','--core',str(core),'--rom',str(out/'test.sfc'),
        '--kind','adapter','--frames','120','--ram',str(out/'memory.ram'),
        '--receipt',str(out/'receipt.json')],capture_output=True,text=True,timeout=30)
    (out/'run.log').write_text(run.stdout+run.stderr)
    run.check_returncode()
    ram = (out/'memory.ram').read_bytes()
    decision_line = int.from_bytes(ram[0x6006:0x6008], 'little')
    allowed = decision_line < (31 if line30 else 30) or decision_line >= 194
    if ram[0x6000:0x6004] != bytes((allowed,0x56,0x78,0xff)):
        raise ValueError('Wrong publication decision or caller state')
    low, high = (44,1) if allowed else (42,0)
    if any(ram[p] != v for p,v in ((0xf6,44),(0x3d,1),(0x1c94,low),(0x1c97,low),
            (0x1c95,high),(0x1c98,high),(0x1c93,127),(0x1c96,35),(0x1c99,45))):
        raise ValueError('Wrong committed/live camera or adjacent table state')
    finish = int.from_bytes(ram[0x6004:0x6006], 'little')
    if decision_line < 31 and finish >= 32:
        raise ValueError('Allowed copy missed first street fetch')
    return dict(line=line,nops=nops,line30=line30,decision_line=decision_line,allowed=allowed,finish_line=finish,
                artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()})


def check(core, out):
    out.mkdir(parents=True, exist_ok=False)
    cases = [case(core,out/f'line-{line}-{nops}',line,nops)
             for line in (0,10,28,29,30,31,32,38,127,158,159,160,192,193,194,200,239,240,250,256,260)
             for nops in (0,20)]
    # Sweep into and across the newly usable line, retaining every case.
    # No input or emulated beam state writes; the fixture burns real cycles.
    cases += [case(core,out/f'boundary-{line}-{nops}',line,nops)
              for line in (29,30,31) for nops in range(4,101,4)]
    if not any(c['decision_line'] == 30 and c['allowed'] for c in cases):
        raise ValueError('No coverage of the newly permitted line')
    cases += [case(core,out/f'default-{line}',line,line30=False)
              for line in (29,30,31,193,194,256)]
    mutants=[]
    for name,line,mutation in (
        ('late-cutoff',38,('cmp #31','cmp #40')),
        ('old-cutoff',30,('cmp #31','cmp #30')),
        ('early-lower-cutoff',193,('cmp #194','cmp #193')),
        ('force-high-bit',38,('and #1\n    bne @high','ora #1\n    bne @high')),
        ('wrong-second-low',10,('sta a:$1C97','sta a:$1C9A')),
        ('missing-high-copy',10,('sta a:$1C98','nop\n    nop\n    nop'))):
        try:
            case(core,out/name,line,mutation=mutation)
        except ValueError as error:
            mutants.append(dict(name=name,rejection=str(error),
                artifacts={str(p):sha(p) for p in (out/name).iterdir() if p.is_file()}))
        else:
            raise ValueError('Camera mutation passed: '+name)
    sources=[Path(__file__),Path('snes/camera_publish_safe.inc'),Path('snes/camera_publish_test.asm'),
             Path('snes/wram_clear.inc'),Path('snes/native_boot.cfg'),Path('tools/smoke_libretro.py'),
             Path('tools/check_oam_live_half.py'),core]
    report=dict(passed=True,cases=cases,mutants=mutants,sources={str(p):sha(p) for p in sources},
        scope='Production copy/guard, real nine-bit beam reads, early/late/rollover boundaries, '
              'complete committed/live camera and adjacent descriptors, X/Y/stack. '
              'Does not certify game cadence or entire hook/retained-NMI integration.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(cases),mutants=len(mutants))))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','out'):p.add_argument('--'+name,type=Path,required=True)
    check(**vars(p.parse_args()))
