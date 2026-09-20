"""Execute current/trial SPC byte transfer and continuous timer-clock checks."""
import argparse
import hashlib
import json
from pathlib import Path
from tools.benchmark_report import sha
from tools.build_receiver_local_poll import patch,ORIGIN
from tools.check_receiver_poll_trial import stream


def check(parent,candidate,core,out):
    if out.exists():raise ValueError('Fresh output required')
    engines=[];sources={}
    for root in (parent,candidate):
        meta=json.loads((root/'manifest.json').read_text());rom=root/'native-cpu.sfc'
        if sha(rom)!=meta['rom_sha256']:raise ValueError('Changed cartridge')
        at=meta['sweep_driver_rom_offset'];size=meta['sweep_driver_layout']['engine_bytes']
        data=rom.read_bytes()[at:at+size]
        if hashlib.sha256(data).hexdigest()!=meta['spc_sha256']:raise ValueError('Changed engine')
        engines.append(data)
        for p in (rom,root/'manifest.json'):sources[str(p)]=sha(p)
    if patch(engines[0])!=engines[1]:raise ValueError('Different trial patch')
    trials={name:[stream(core,data,meta['sweep_driver_layout'],mode,delay)
        for mode in (0,128) for delay in (0,256,512,2048)]
        for name,data in zip(('before','after'),engines)}
    bad=bytearray(engines[1]);bad[ORIGIN-0x400+4:ORIGIN-0x400+7]=bytes(3)
    mutant=stream(core,bytes(bad),meta['sweep_driver_layout'],0,2048)
    passed=all(r['passed'] and not r['bad_volume_writes'] for arm in trials.values() for r in arm) and not mutant['passed']
    for p in (Path(__file__),Path('tools/build_receiver_local_poll.py'),Path('tools/check_receiver_poll_trial.py'),
        Path('tools/check_sweep_driver.py'),Path('tools/spc_sweep_driver_probe.inc'),core):sources[str(p)]=sha(p)
    for name in ('core.cpp','smp.cpp','memory.cpp','timing.cpp'):
        p=core.parent.parent/'apu/bapu/smp'/name;sources[str(p)]=sha(p)
    summary={name:[dict(mode=r['mode'],delay=r['delay'],passed=r['passed'],
        minimum=min(r['packet_clocks']),mean=sum(r['packet_clocks'])/len(r['packet_clocks']),
        maximum=max(r['packet_clocks'])) for r in arm] for name,arm in trials.items()}
    out.mkdir();(out/'report.json').write_text(json.dumps(dict(passed=passed,trials=trials,
        summary=summary,mutant=mutant,mutant_rejected=not mutant['passed'],sources=sources,
        release_ready=False,scope='16 actual-interpreter cases;101 packets then one second idle. Both frame modes, four sender delays. Not arbitrary-byte fidelity, full-game speed or acoustic acceptance.'),indent=2)+'\n')
    print(json.dumps(dict(passed=passed,summary=summary,mutant_rejected=not mutant['passed'])))
    if not passed:raise ValueError('Actual SPC regression')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','candidate','core','out'):p.add_argument('--'+k,type=Path,required=True)
    check(**vars(p.parse_args()))
