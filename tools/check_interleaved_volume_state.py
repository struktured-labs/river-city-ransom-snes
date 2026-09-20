"""Executed interleaved-volume state and timing, with explicit writer ownership."""
import argparse
from collections import Counter
import json
from pathlib import Path
import time

from tools import check_compact_startup_pitch as state
from tools import check_receiver_poll_trial as receiver
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_compact_startup_pitch import FLUSH
from tools.build_interleaved_restart_volume import patch, ORIGIN
from tools.build_restart_volume_trial import VOLUMES
from tools.check_inline_pitch_trial import cases
from tools.check_sweep_driver import Driver


class VolumeDriver(Driver):
    def load(self):
        d=self.layout['driver']
        # The probe API accepts one contiguous ownership interval. Extend its
        # upper end over the appended helpers/flush in this exact hashed engine;
        # do not disable the check. An executed legacy-writer mutant below must
        # still trip it. This is not a whitelist of individual instruction PCs.
        self.invoke('load',self.image,len(self.image),d['half_pair'],d['publish'],0x3540)


def check(core,parent,fixture,out):
    started=time.monotonic()
    if out.exists(): raise ValueError('Fresh qualification required')
    meta=json.loads((parent/'manifest.json').read_text()); layout=meta['sweep_driver_layout']
    if sha(parent/'native-cpu.sfc')!=meta['rom_sha256']:raise ValueError('Changed parent')
    at=meta['sweep_driver_rom_offset']; image=(parent/'native-cpu.sfc').read_bytes()
    baseline,trial,detail=patch(image[at:at+layout['engine_bytes']],layout)
    for name,engine in [('baseline',baseline),('trial',trial)]:
        bound_report(fixture/name/'manifest.json')
        if (fixture/name/'engine.bin').read_bytes()!=engine:raise ValueError('Changed fixture')
    selected=[]
    for dp in cases():
        for mask in range(4):
            item=bytearray(dp);item[0x54]=mask;selected.append(item)
    old_state,old_receiver=state.Driver,receiver.Driver
    try:
        state.Driver=receiver.Driver=VolumeDriver
        before=state.execute(core,baseline,layout,FLUSH,selected)
        after=state.execute(core,trial,layout,FLUSH,selected)
        mismatches=[i for i,(a,b) in enumerate(zip(before,after)) if a[0]!=b[0]]
        costs={str(mask):dict(Counter(b[1]-a[1] for dp,a,b in zip(selected,before,after) if dp[0x54]==mask)) for mask in range(4)}
        bad=bytearray(trial);at=detail['labels']['volume1']-0x400
        if bad[at:at+3]!=bytes((0xe5,(VOLUMES+1)&255,(VOLUMES+1)>>8)):raise ValueError('Changed source mutation site')
        bad[at+1]=VOLUMES&255
        subset=selected[-4452:]
        expected=state.execute(core,baseline,layout,FLUSH,subset)
        wrong=state.execute(core,bytes(bad),layout,FLUSH,subset)
        wrong_volume=sum(a[0]!=b[0] for a,b in zip(expected,wrong))
        continuous={name:[receiver.stream(core,engine,layout,mode,delay) for mode in (0,128) for delay in (0,256,512,2048)]
            for name,engine in [('baseline',baseline),('trial',trial)]}
        bad=bytearray(trial)
        if bad[0x177]!=0xac:raise ValueError('Changed suppressed legacy volume store')
        bad[0x177]=0xf3
        legacy=receiver.stream(core,bytes(bad),layout,0,2048)
    finally:
        state.Driver,receiver.Driver=old_state,old_receiver
    passed=not mismatches and bool(wrong_volume) and bool(legacy['bad_volume_writes']) and all(
        r['passed'] and not r['bad_volume_writes'] for arm in continuous.values() for r in arm)
    paths=[Path(__file__),Path('tools/build_interleaved_restart_volume.py'),Path('tools/build_restart_volume_trial.py'),
        Path('tools/check_compact_startup_pitch.py'),Path('tools/check_inline_pitch_trial.py'),
        Path('tools/check_receiver_poll_trial.py'),Path('tools/check_sweep_driver.py'),
        Path('tools/check_startup_pitch_state.py'),Path('tools/spc_sweep_driver_probe.inc'),
        core,parent/'manifest.json',parent/'native-cpu.sfc']
    paths += [fixture/arm/name for arm in ('baseline','trial') for name in ('manifest.json','engine.bin')]
    paths += [core.parent.parent/'apu/bapu/smp'/n for n in ('core.cpp','smp.cpp','memory.cpp','timing.cpp')]
    report=dict(passed=passed,cases=len(selected),mismatches=mismatches,added_clocks_by_pending_mask=costs,
        continuous=continuous,wrong_volume_mutant_failures=wrong_volume,legacy_writer_mutant=legacy,
        volume_writer_interval=[layout['driver']['publish'],0x3540],
        sources={str(p):sha(p) for p in paths},elapsed_seconds=time.monotonic()-started,
        release_ready=False,scope=__doc__+' All final DSP and DP except F2/F3; '
        'bounded ownership interval includes original and relocated writers. Not waveform or game timing proof.')
    out.mkdir();(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('sources','continuous','legacy_writer_mutant','mismatches')}))
    if not passed:raise ValueError('Interleaved state/timer gate failed')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','parent','fixture','out'):p.add_argument('--'+name,type=Path,required=True)
    check(**vars(p.parse_args()))
