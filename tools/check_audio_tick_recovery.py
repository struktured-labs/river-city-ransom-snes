"""Execute recurring timer recovery across masked critical sections, not sound synthesis."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import time
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

CASES=(('ordinary_irq',0,0,()),('restore_before',1,60,()),
       ('recover_after',2,110,()),('recover_at_nmi',3,250,()),
       ('missing_recovery',2,110,('OMIT_RECOVERY',)),
       ('duplicate_service',2,110,('DUPLICATE_SERVICE',)),
       ('clobbered_x',2,110,('CLOBBER_X',)))


def assess(ram,mode,resume):
    if len(ram)<0x1a09:raise ValueError('Incomplete WRAM')
    tokens=[ram[0x1900+i]|ram[0x1920+i]<<8 for i in range(32)]
    lines=[ram[0x1940+i]|ram[0x1960+i]<<8 for i in range(32)]
    routes=list(ram[0x1980:0x19a0])
    expected_route=1 if mode in (0,1) else 2 if mode==2 else 3
    target=80 if mode in (0,1) else resume
    expected=[(0xfffd+i)&65535 for i in range(32)]
    checks=dict(complete=ram[0x1810]==1,nmi_epochs=ram[0x1806]==33,
        actual_calls=ram[0x1809]==32,ordered_unique_tokens=tokens==expected,
        no_overflow=ram[0x1808]==0,finished_pending=ram[0x1800]==0,
        source_routes=routes==[expected_route]*32,
        service_timing=all(target<=v<=target+3 for v in lines),
        a=ram[0x1a00:0x1a02]==bytes.fromhex('cdab'),x=ram[0x1a02]==0x78,
        y=ram[0x1a03]==0xbc,flags=ram[0x1a04]&0x3d==0x39,
        db=ram[0x1a05]==0x7e,direct_page=ram[0x1a06:0x1a08]==bytes.fromhex('3412'),
        stack=ram[0x1a08]==0xff)
    if mode in (0,1):
        checks.update(irq_count=ram[0x1805]==32,ack_seen=bool(ram[0x180a]&128),
                      ack_cleared=not ram[0x180b]&128)
    else:checks['no_spurious_irq']=ram[0x1805]==0
    return dict(checks=checks,failures=[k for k,v in checks.items() if not v],
        tokens=tokens,lines=lines,routes=routes,nmi_count=ram[0x1806],irq_count=ram[0x1805])


def check(core,out):
    if out.exists():raise ValueError('Fresh output required')
    started=time.monotonic()
    sources={str(p):sha(p) for p in (Path(__file__),Path('snes/audio_tick_recovery_test.asm'),
        Path('snes/native_boot.cfg'),Path('tools/build_inline_pitch_trial.py'),
        Path('tools/smoke_libretro.py'),Path('.deps/cc65/bin/ca65'),Path('.deps/cc65/bin/ld65'),core)}
    out.mkdir(parents=True)
    def run(case):
        name,mode,resume,mutations=case;folder=out/name;folder.mkdir()
        defs=[f'MODE={mode}',f'RESUME_LINE={resume}',*mutations]
        subprocess.run(['.deps/cc65/bin/ca65',*[v for d in defs for v in ('-D',d)],
            '-o',str(folder/'test.o'),'snes/audio_tick_recovery_test.asm'],check=True,capture_output=True)
        subprocess.run(['.deps/cc65/bin/ld65','-C','snes/native_boot.cfg','-Ln',str(folder/'test.lbl'),
            '-o',str(folder/'test.bin'),str(folder/'test.o')],check=True,capture_output=True)
        image=bytearray(0x200000);image[0x8000:0x10000]=(folder/'test.bin').read_bytes();checksum(image)
        (folder/'test.sfc').write_bytes(image)
        r=subprocess.run([sys.executable,'-m','tools.smoke_libretro','--core',str(core),
            '--rom',str(folder/'test.sfc'),'--kind','render','--frames','120',
            '--ram',str(folder/'memory.ram'),'--receipt',str(folder/'capture.json')],
            capture_output=True,text=True,timeout=30)
        (folder/'execution.log').write_text(r.stdout+r.stderr);r.check_returncode()
        result=assess((folder/'memory.ram').read_bytes(),mode,resume)
        required={'missing_recovery':{'service_timing','source_routes'},
            'duplicate_service':{'ordered_unique_tokens','no_overflow'},'clobbered_x':{'x'}}.get(name,set())
        result.update(name=name,mutation=list(mutations),
            expected_outcome=required.issubset(result['failures']) if required else not result['failures'],
            artifacts={str(p):sha(p) for p in folder.iterdir() if p.suffix in ('.sfc','.ram','.json','.lbl','.log')})
        return result
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(run,CASES))
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Changed source')
    report=dict(passed=all(r['expected_outcome'] for r in results),variants=results,sources=sources,
        seconds=time.monotonic()-started,release_ready=False,game_integration_verified=False,
        scope=__doc__+' E=1 only, real32 NMI-generated tokens including16-bit wrap. '
        'Service is an explicitly destructive spy, not an APU driver or a proof of acoustic quality. '
        'Late NMI fallback remains late; accounting alone does not pass a deadline.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'],seconds=report['seconds'],
        variants=[{k:r[k] for k in ('name','failures','lines','expected_outcome')} for r in results])))
    return report['passed']


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('core','out'):p.add_argument('--'+k,type=Path,required=True)
    raise SystemExit(0 if check(**vars(p.parse_args())) else 1)
