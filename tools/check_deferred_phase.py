"""Execute the production retained-NMI phase guard at actual beam boundaries."""
import argparse
import json
from pathlib import Path
import subprocess

from tools.benchmark_report import sha
from tools.check_oam_live_half import checksum


def case(core,out,line,threshold,nops=0,mutation=None):
    out.mkdir(parents=True,exist_ok=False)
    source=Path('snes/native_boot.asm').read_text()
    helper='phase_policy:\n@deferred_late_vblank:'+source.split('@deferred_late_vblank:',1)[1].split('@deferred_late_vblank_done:',1)[0]
    helper+='@deferred_late_vblank_done:\n    rts\n'
    if mutation:
        old,new=mutation
        if helper.count(old)!=1:raise ValueError('Nonunique phase mutation')
        helper=helper.replace(old,new)
    (out/'phase.inc').write_text(helper)
    fixture=Path('snes/camera_publish_test.asm').read_text().replace(
        'jsr camera_publish_safe','jsr phase_policy').replace(
        '.include "camera_publish_safe.inc"','.include "phase.inc"')
    (out/'test.asm').write_text(fixture)
    subprocess.run(['.deps/cc65/bin/ca65','-D',f'TARGET_LINE={line}',
        '-D',f'DELAY_NOPS={nops}','-D',f'DEFERRED_RESUME_LINE={threshold}',
        '-I','snes','-o',str(out/'test.o'),str(out/'test.asm')],check=True,capture_output=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/native_boot.cfg','-o',str(out/'test.bin'),
        str(out/'test.o')],check=True,capture_output=True)
    rom=bytearray(2*1024*1024)
    rom[0x8000:0x10000]=(out/'test.bin').read_bytes()
    (out/'test.sfc').write_bytes(checksum(rom))
    result=subprocess.run(['python3','tools/smoke_libretro.py','--core',str(core),
        '--rom',str(out/'test.sfc'),'--kind','adapter','--frames','120',
        '--ram',str(out/'memory.ram'),'--receipt',str(out/'receipt.json')],
        capture_output=True,text=True,timeout=30)
    (out/'run.log').write_text(result.stdout+result.stderr)
    result.check_returncode()
    ram=(out/'memory.ram').read_bytes()
    finish=int.from_bytes(ram[0x6004:0x6006],'little')
    earliest=max(line,threshold)
    if not earliest<=finish<=earliest+1:
        raise ValueError('Phase guard returned outside expected beam interval')
    if ram[0x6001:0x6004]!=bytes.fromhex('5678ff'):
        raise ValueError('Phase guard changed X/Y/stack')
    if ram[0x1ced:0x1cef]!=b'\0\0' or ram[0x1c94]!=42 or ram[0xf6]!=44:
        raise ValueError('Phase guard changed unrelated publication state')
    return dict(line=line,threshold=threshold,nops=nops,finish=finish,
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()})


def run(core,out):
    out.mkdir(parents=True,exist_ok=False)
    sources={str(p):sha(p) for p in (Path(__file__),Path('snes/native_boot.asm'),
        Path('snes/native_boot.cfg'),Path('snes/camera_publish_test.asm'),
        Path('snes/wram_clear.inc'),Path('tools/smoke_libretro.py'),core)}
    positives=[case(core,out/f'{threshold}-{line}-{nops}',line,threshold,nops)
        for threshold in (240,250) for line in (230,239,240,241,249,250,255,256,260)
        for nops in (0,20)]
    negatives=[]
    for name,line,change in (
        ('early-cutoff',230,('cmp #DEFERRED_RESUME_LINE','cmp #230')),
        ('forced-high-bit',230,('and #1','ora #1')),
        ('ignored-high-bit',256,('and #1','and #0')),
        ('wrong-scratch',249,('sta a:$1CEC','sta a:$1CED'))):
        try:case(core,out/name,line,250,mutation=change)
        except ValueError as error:
            negatives.append(dict(name=name,error=str(error),
                artifacts={str(p):sha(p) for p in (out/name).iterdir() if p.is_file()}))
        else:raise ValueError('Unsafe phase mutant survived: '+name)
    if sources!={str(p):sha(p) for p in map(Path,sources)}:
        raise ValueError('Phase sources changed')
    report=dict(passed=True,cases=positives,mutants=negatives,sources=sources,
        scope='Extracted production nine-bit phase guard, two thresholds and instruction offsets, '
              'actual beam230..260, X/Y/stack and unrelated publication-state preservation. '
              'No assertion of whole-NMI scheduling, original game speed or audio cadence.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(positives),mutants=len(negatives))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','out'):p.add_argument('--'+name,type=Path,required=True)
    run(**vars(p.parse_args()))
