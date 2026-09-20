"""Execute token-first receiver clock/ownership checks with actual broken controls."""
import argparse
import json
from pathlib import Path
import time
from tools import check_receiver_poll_trial as receiver
from tools.check_interleaved_volume_state import VolumeDriver
from tools.build_receiver_token_priority import patch,ORIGIN,CODE
from tools.benchmark_report import sha

def check(parent,candidate,core,out):
    start=time.monotonic()
    if out.exists():raise ValueError('Fresh output required')
    engines=[];sources={}
    for root in (parent,candidate):
        meta=json.loads((root/'manifest.json').read_text());rom=root/'native-cpu.sfc'
        if sha(rom)!=meta['rom_sha256']:raise ValueError('Changed cartridge')
        at=meta['sweep_driver_rom_offset'];size=meta['sweep_driver_layout']['engine_bytes']
        engines.append(rom.read_bytes()[at:at+size])
        for p in (rom,root/'manifest.json'):sources[str(p)]=sha(p)
    if patch(engines[0])!=engines[1]:raise ValueError('Different patch')
    previous=receiver.Driver
    try:
        receiver.Driver=VolumeDriver
        trials={name:[receiver.stream(core,e,meta['sweep_driver_layout'],mode,delay)
            for mode in (0,128) for delay in (0,256,512,2048)]
            for name,e in zip(('parent','trial'),engines)}
        bad=bytearray(engines[1]);at=ORIGIN-0x400+8
        if bad[at:at+3]!=bytes.fromhex('3f8432'):raise ValueError('Wrong timer mutant')
        bad[at:at+3]=bytes(3)
        timer=receiver.stream(core,bytes(bad),meta['sweep_driver_layout'],0,2048)
        bad=bytearray(engines[1]);bad[0x177]=0xf3
        legacy=receiver.stream(core,bytes(bad),meta['sweep_driver_layout'],0,2048)
    finally:receiver.Driver=previous
    passed=all(x['passed'] and not x['bad_volume_writes'] for arm in trials.values() for x in arm) and not timer['passed'] and bool(legacy['bad_volume_writes'])
    paths=[Path(__file__),Path('tools/build_receiver_token_priority.py'),Path('tools/check_receiver_poll_trial.py'),Path('tools/check_interleaved_volume_state.py'),Path('tools/check_sweep_driver.py'),Path('tools/spc_sweep_driver_probe.inc'),core]
    paths += [core.parent.parent/'apu/bapu/smp'/n for n in ('core.cpp','smp.cpp','memory.cpp','timing.cpp')]
    sources.update({str(p):sha(p) for p in paths})
    report=dict(passed=passed,trials=trials,timer_drop=timer,legacy_writer=legacy,sources=sources,seconds=time.monotonic()-start,scope=__doc__,release_ready=False)
    out.mkdir();(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=passed,seconds=report['seconds'],timer_rejected=not timer['passed'],legacy_rejected=bool(legacy['bad_volume_writes']))))
    if not passed:raise ValueError('SPC regression')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','candidate','core','out'):p.add_argument('--'+k,type=Path,required=True)
    check(**vars(p.parse_args()))
