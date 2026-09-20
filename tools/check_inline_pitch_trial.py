"""Executed state/cost and live-clock qualification for the inline pitch trial."""
import argparse
import hashlib
import json
from pathlib import Path

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import patch
from tools.check_pitch_pair_trial import run_cases
from tools.check_receiver_poll_trial import stream
from tools.check_sweep_driver import Driver


def cases():
    for voice in (0,1):
        for period in range(2048):
            for control in (0,8,0x80,0x87,0x94,0xff):
                for enabled in (0,1):
                    dp=bytearray(256);lo=(0x7a,0x83)[voice]
                    dp[lo]=period&255;dp[lo+1]=period>>8
                    dp[0x55]=enabled<<voice;dp[0x40+4*voice]=0x3f;dp[0x41+4*voice]=control
                    yield dp
    for voice in (0,1):
        for constant in (0,1):
            for level in range(17):
                for raw in range(16):
                    dp=bytearray(256);dp[(0x7a,0x83)[voice]]=172
                    dp[0x55]=1<<voice;dp[0x40+4*voice]=raw|(constant<<4)
                    dp[0x41+4*voice]=8;dp[0x86+3*voice]=level
                    yield dp
    for first in (8,255,256,1023,2047):
        for second in (8,255,256,1023,2047):
            dp=bytearray(256);dp[0x55]=3
            for voice,period in enumerate((first,second)):
                lo=(0x7a,0x83)[voice];dp[lo]=period&255;dp[lo+1]=period>>8
                dp[0x40+4*voice]=0x3f;dp[0x41+4*voice]=8
            yield dp


def run(core,engine,layout):
    driver=Driver(core,engine,layout);results=[]
    for dp in cases():
        driver.seed(dp);before=driver.out[384];driver.call('publish')
        results.append((hashlib.sha256(bytes(driver.out[:384])).hexdigest(),driver.out[384]-before))
    return results


def check(parent,trial,core,out):
    proof=bound_report(trial/'report.json')
    game=json.loads((parent/'manifest.json').read_text());layout=game['sweep_driver_layout']
    engines=[(trial/name/'engine.bin').read_bytes() for name in ('baseline','trial')]
    rebuilt,metadata=patch(engines[0],layout)
    if rebuilt!=engines[1] or hashlib.sha256(engines[0]).hexdigest()!=game['spc_sha256']:
        raise ValueError('Executed engines do not match parent/patch')
    before=run(core,engines[0],layout);after=run(core,engines[1],layout)
    errors=[i for i,(a,b) in enumerate(zip(before,after)) if a[0]!=b[0]]
    delta=sorted(set(b[1]-a[1] for a,b in zip(before,after)))
    mutated=bytearray(engines[1])
    for c in metadata['changes']:
        at=c['offset']+15
        if mutated[at:at+2]!=bytes.fromhex('d8f3'):raise ValueError('Wrong mutation site')
        mutated[at]=0xc4 # Write the low value again instead of the prefetched high.
    original=run_cases(core,engines[0],layout);wrong=run_cases(core,bytes(mutated),layout)
    rejected=sum(a[0]!=b[0] for a,b in zip(original,wrong))
    continuous={name:[stream(core,engine,layout,mode,delay) for mode in (0,128)
        for delay in (0,256,512,2048)] for name,engine in zip(('baseline','trial'),engines)}
    passed=not errors and bool(rejected) and delta==[0,1,2] and all(
        r['passed'] and not r['bad_volume_writes'] for rows in continuous.values() for r in rows)
    paths=[Path(__file__),Path('tools/build_inline_pitch_trial.py'),Path('tools/check_sweep_driver.py'),
        Path('tools/check_pitch_pair_trial.py'),Path('tools/check_receiver_poll_trial.py'),
        Path('tools/spc_sweep_driver_probe.inc'),core,parent/'manifest.json',trial/'report.json',
        trial/'baseline/engine.bin',trial/'trial/engine.bin']
    paths.extend(core.parent.parent/'apu/bapu/smp'/n for n in ('core.cpp','smp.cpp','memory.cpp','timing.cpp'))
    report=dict(passed=passed,cases=len(before),state_errors=errors,added_spc_clocks=delta,
        wrong_high_mutant_failures=rejected,continuous=continuous,sources={str(p):sha(p) for p in paths},
        scope='All 11-bit periods, both voices, six sweep controls and enable states; all constant/envelope '
        'levels; 25 two-voice boundary cases. Complete DP/final DSP equality, actual cost and delayed '
        'packet clock checks. CPU X/Y scratch ABI and full-game caller behavior require separate evidence. '
        'Not atomic pitch, pop-free sound, physical verification or a release approval.')
    out.mkdir(parents=True,exist_ok=False);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('passed','cases','state_errors','added_spc_clocks','wrong_high_mutant_failures')}))
    if not passed:raise ValueError('Inline pitch state/cost/clock regression')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','trial','core','out'):p.add_argument('--'+name,type=Path,required=True)
    check(**vars(p.parse_args()))
