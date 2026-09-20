"""Execute both real SPC publishers for every NES pulse period and both voices."""
import argparse
import json
from pathlib import Path

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_pitch_pair_trial import patch
from tools.check_sweep_driver import Driver


def run_cases(core,engine,layout):
    run=Driver(core,engine,layout)
    result=[]
    for voice in (0,1):
        for period in range(2048):
            dp=bytearray(256);lo=(0x7a,0x83)[voice]
            dp[lo]=period&255;dp[lo+1]=period>>8
            dp[0x55]=1<<voice;dp[0x40+4*voice]=0x1f;dp[0x41+4*voice]=0x98
            run.seed(dp)
            before=run.out[384]
            run.call('publish')
            result.append((list(run.out[:384]),run.out[384]-before))
    return result


def check(core,parent,fixture,out):
    game=json.loads((parent/'manifest.json').read_text())
    player=bound_report(fixture/'manifest.json')
    cart=(parent/'native-cpu.sfc').read_bytes()
    at=game['sweep_driver_rom_offset'];size=game['sweep_driver_layout']['engine_bytes']
    original=cart[at:at+size]
    candidate,meta=patch(original,game['sweep_driver_layout'])
    if sha(parent/'native-cpu.sfc')!=game['rom_sha256'] or candidate!=(fixture/'engine.bin').read_bytes():
        raise ValueError('Executed engine does not equal replay engine')
    before=run_cases(core,original,game['sweep_driver_layout'])
    after=run_cases(core,candidate,game['sweep_driver_layout'])
    errors=[i for i,(a,b) in enumerate(zip(before,after)) if a[0]!=b[0]]
    deltas=sorted(set(b[1]-a[1] for a,b in zip(before,after)))
    # Negative control: store A (low) instead of Y (prefetched high).
    bad=bytearray(candidate)
    for voice in (0,1):
        at=0x2ba0+voice*0x20+17
        if bad[at:at+2]!=bytes.fromhex('cbf3'):raise ValueError('Mutant site changed')
        bad[at]=0xc4
    mutant=run_cases(core,bytes(bad),game['sweep_driver_layout'])
    failures=[i for i,(a,b) in enumerate(zip(before,mutant)) if a[0]!=b[0]]
    sources=[Path(__file__),Path('tools/build_pitch_pair_trial.py'),Path('tools/check_sweep_driver.py'),
        Path('tools/spc_sweep_driver_probe.inc'),core,parent/'manifest.json',parent/'native-cpu.sfc',fixture/'manifest.json']
    tree=core.parent.parent
    sources.extend(tree/'apu/bapu/smp'/n for n in ('core.cpp','smp.cpp','memory.cpp','timing.cpp'))
    report=dict(passed=not errors and bool(failures),cases=len(before),errors=errors,
        added_spc_clocks=deltas,mutant_failed_cases=len(failures),
        sources={str(p):sha(p) for p in sources},
        scope='4096 actual SPC calls, both voices and every 11-bit period at constant volume, '
              'compare all DP RAM and final DSP registers. Wrong-high-byte mutant executed. '
              'Not all controls, CPU register ABI, game speed, analog fidelity or hardware validation.')
    out.mkdir(parents=True,exist_ok=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='sources'}))
    if not report['passed']:raise ValueError('Publisher equivalence failed')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','parent','fixture','out'):p.add_argument('--'+name,type=Path,required=True)
    check(**vars(p.parse_args()))
