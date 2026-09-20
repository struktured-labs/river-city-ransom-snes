"""Execute baseline/trial polling with actual SPC interpreter and hardware timers."""
import argparse
import hashlib
import json
from pathlib import Path

from tools.benchmark_report import sha
from tools.build_receiver_dispatch_trial import patch
from tools.check_receiver_poll_trial import stream


def check(parent,candidate,core,out):
    if out.exists():raise ValueError('Need fresh evidence')
    manifests=[json.loads((p/'manifest.json').read_text()) for p in (parent,candidate)]
    engines=[]
    for p,m in zip((parent,candidate),manifests):
        if sha(p/'native-cpu.sfc')!=m['rom_sha256']:raise ValueError('Changed cartridge')
        at=m['sweep_driver_rom_offset'];size=m['sweep_driver_layout']['engine_bytes']
        engine=(p/'native-cpu.sfc').read_bytes()[at:at+size]
        if hashlib.sha256(engine).hexdigest()!=m['spc_sha256']:raise ValueError('Changed engine')
        engines.append(engine)
    layout=manifests[0]['sweep_driver_layout']
    rebuilt,metadata=patch(engines[0],layout,manifests[0]['receiver_poll'])
    if rebuilt!=engines[1]:raise ValueError('Trial is not exact patch')
    trials={name:[stream(core,engine,layout,mode,delay) for mode in (0,128)
                  for delay in (0,256,512,2048)]
            for name,engine in zip(('baseline','trial'),engines)}
    bad=bytearray(engines[1]);at=metadata['helper']-0x400+4
    if bad[at]!=0x3f:raise ValueError('Missing negative-control call')
    bad[at:at+3]=bytes(3)
    mutant=stream(core,bytes(bad),layout,0,2048)
    passed=all(r['passed'] and not r['bad_volume_writes'] for side in trials.values() for r in side) and not mutant['passed']
    paths=[Path(__file__),Path('tools/build_receiver_dispatch_trial.py'),
        Path('tools/check_receiver_poll_trial.py'),Path('tools/check_sweep_driver.py'),
        Path('tools/spc_sweep_driver_probe.inc'),core,
        parent/'manifest.json',parent/'native-cpu.sfc',candidate/'manifest.json',candidate/'native-cpu.sfc']
    paths.extend(core.parent.parent/'apu/bapu/smp'/name for name in ('core.cpp','smp.cpp','memory.cpp','timing.cpp'))
    report=dict(passed=passed,trials=trials,mutant=mutant,mutant_rejected=not mutant['passed'],
        sources={str(p):sha(p) for p in paths},
        scope='16 executed cases: 101 packets then one second idle, two frame modes and four '
        'sender delays. Continuous half-frame deadlines and unintended volume writes checked. '
        'Not whole-game speed, arbitrary-input byte fidelity or perceptual audio proof.')
    out.mkdir(parents=True,exist_ok=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=passed,mutant_rejected=report['mutant_rejected'],costs={
        name:[dict(mode=r['mode'],delay=r['delay'],minimum=min(r['packet_clocks']),
                   mean=sum(r['packet_clocks'])/len(r['packet_clocks']),maximum=max(r['packet_clocks']))
              for r in rows] for name,rows in trials.items()})))
    if not passed:raise ValueError('Executed receiver regression')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','candidate','core','out'):p.add_argument('--'+name,type=Path,required=True)
    check(**vars(p.parse_args()))
