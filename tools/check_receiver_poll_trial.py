"""Execute actual receiver polling under delayed packets and continuous sweep clocks."""
import argparse
import json
from pathlib import Path

from tools.benchmark_report import sha
from tools.build_receiver_poll_trial import patch
from tools.check_sweep_driver import Driver, audit_deadlines


def stream(core,engine,layout,mode,delay):
    run=Driver(core,engine,layout);run.boot()
    packet=bytearray(23);packet[:8]=bytes((0x3f,0x94,172,0,0x3f,0x94,172,0))
    packet[20]=63|64|mode;packet[21]=3;packet[22]=195
    run.packet(packet,0);epoch=run.out[387]
    packet[20]=63|mode;packet[22]=0
    costs=[]
    for _ in range(100):
        start=run.out[384];run.packet(packet,delay);costs.append(run.out[384]-start)
    run.wait(1025280)
    events=run.events();result=audit_deadlines(events,epoch,run.out[384],mode)
    return dict(**result,mode=mode,delay=delay,epoch=epoch,end=run.out[384],
        packet_clocks=costs,events=events,bad_volume_writes=run.out[386])


def check(parent,candidate,core,out):
    before=json.loads((parent/'manifest.json').read_text());after=json.loads((candidate/'manifest.json').read_text())
    engines=[]
    for root,m in ((parent,before),(candidate,after)):
        if sha(root/'native-cpu.sfc')!=m['rom_sha256']:raise ValueError('Changed game cartridge')
        data=(root/'native-cpu.sfc').read_bytes();at=m['sweep_driver_rom_offset'];size=m['sweep_driver_layout']['engine_bytes']
        engines.append(data[at:at+size])
    rebuilt,metadata=patch(engines[0],before['sweep_driver_layout'])
    if rebuilt!=engines[1]:raise ValueError('Test engine differs from cartridge patch')
    trials={}
    for name,engine in zip(('baseline','candidate'),engines):
        trials[name]=[stream(core,engine,before['sweep_driver_layout'],mode,delay)
            for mode in (0,128) for delay in (0,256,512,2048)]
    bad=bytearray(engines[1]);offset=metadata['helper_spc']-0x400+4
    if bad[offset]!=0x3f:raise ValueError('Mutant call missing')
    bad[offset:offset+3]=bytes(3)
    mutant=stream(core,bytes(bad),before['sweep_driver_layout'],0,2048)
    paths=[Path(__file__),Path('tools/build_receiver_poll_trial.py'),Path('tools/check_sweep_driver.py'),
        Path('tools/spc_sweep_driver_probe.inc'),core,parent/'manifest.json',parent/'native-cpu.sfc',
        candidate/'manifest.json',candidate/'native-cpu.sfc']
    paths.extend(core.parent.parent/'apu/bapu/smp'/n for n in ('core.cpp','smp.cpp','memory.cpp','timing.cpp'))
    report=dict(passed=all(r['passed'] and not r['bad_volume_writes'] for side in trials.values() for r in side)
        and not mutant['passed'],trials=trials,mutant=mutant,mutant_rejected=not mutant['passed'],
        sources={str(p):sha(p) for p in paths},
        scope='Actual deployed/trial SPC engines, real boot and hardware timers. Each case:101 paired '
              'packets,100 without counter reset, then one second idle. Four sender delays and both '
              'frame modes. Continuous half-frame deadlines checked through receive stalls, not just '
              'after reset. Dropped consumed timer delta mutant must fail. Not waveform or game-speed proof.')
    out.mkdir(parents=True,exist_ok=False);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'],mutant_rejected=report['mutant_rejected'],trials={
        k:[dict(mode=r['mode'],delay=r['delay'],passed=r['passed'],packet_min=min(r['packet_clocks']),
            packet_max=max(r['packet_clocks']),deadline_min=min(r['deadline_offsets']),
            deadline_max=max(r['deadline_offsets'])) for r in side] for k,side in trials.items()})))
    if not report['passed']:raise ValueError('Receiver clock regression')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','candidate','core','out'):p.add_argument('--'+name,type=Path,required=True)
    check(**vars(p.parse_args()))
