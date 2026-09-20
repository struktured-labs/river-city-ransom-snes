"""Execute restart-volume final-state, muted-state, and real receiver checks."""
import argparse
from collections import Counter
import json
from pathlib import Path
import time

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_compact_startup_pitch import FLUSH
from tools.build_restart_volume_trial import patch, VOLUMES
from tools.check_compact_startup_pitch import execute
from tools.check_inline_pitch_trial import cases
from tools.check_receiver_poll_trial import stream


def check(core,parent,fixture,out):
    started = time.monotonic()
    if out.exists(): raise ValueError('Fresh state report required')
    meta = json.loads((parent/'manifest.json').read_text())
    image = (parent/'native-cpu.sfc').read_bytes()
    if sha(parent/'native-cpu.sfc') != meta['rom_sha256']: raise ValueError('Changed cartridge')
    at = meta['sweep_driver_rom_offset']; layout = meta['sweep_driver_layout']
    baseline,trial,detail = patch(image[at:at+layout['engine_bytes']],layout)
    for name,engine in [('baseline',baseline),('trial',trial)]:
        bound_report(fixture/name/'manifest.json')
        if (fixture/name/'engine.bin').read_bytes()!=engine: raise ValueError('Changed fixture')
    selected = []
    for dp in cases():
        for mask in range(4):
            item = bytearray(dp); item[0x54]=mask; selected.append(item)
    before = execute(core,baseline,layout,FLUSH,selected)
    after = execute(core,trial,layout,FLUSH,selected)
    mismatches = [i for i,(a,b) in enumerate(zip(before,after)) if a[0]!=b[0]]
    costs = {str(mask):dict(Counter(b[1]-a[1] for dp,a,b in zip(selected,before,after) if dp[0x54]==mask)) for mask in range(4)}
    # Break the late volume source for voice 1; both stored volumes can differ.
    wrong = bytearray(trial); site = detail['late']-0x400+10
    if wrong[site]!=(VOLUMES+1)&255: raise ValueError('Changed mutation site')
    wrong[site]=VOLUMES&255
    subset = selected[-4452:]
    good = execute(core,baseline,layout,FLUSH,subset)
    bad = execute(core,bytes(wrong),layout,FLUSH,subset)
    rejected = sum(a[0]!=b[0] for a,b in zip(good,bad))
    continuous = {name:[stream(core,engine,layout,mode,delay) for mode in (0,128) for delay in (0,256,512,2048)]
        for name,engine in [('baseline',baseline),('trial',trial)]}
    passed = not mismatches and bool(rejected) and all(r['passed'] and not r['bad_volume_writes'] for arm in continuous.values() for r in arm)
    paths = [Path(__file__),Path('tools/build_restart_volume_trial.py'),Path('tools/check_compact_startup_pitch.py'),
        Path('tools/check_inline_pitch_trial.py'),Path('tools/check_startup_pitch_state.py'),
        Path('tools/check_receiver_poll_trial.py'),Path('tools/check_sweep_driver.py'),
        Path('tools/spc_sweep_driver_probe.inc'),core,parent/'manifest.json',parent/'native-cpu.sfc']
    paths += [fixture/name/file for name in ('baseline','trial') for file in ('manifest.json','engine.bin')]
    paths += [core.parent.parent/'apu/bapu/smp'/name for name in ('core.cpp','smp.cpp','memory.cpp','timing.cpp')]
    report = dict(passed=passed,cases=len(selected),mismatches=mismatches,added_clocks_by_pending_mask=costs,
        wrong_volume_mutant_cases=len(subset),wrong_volume_mutant_failures=rejected,continuous=continuous,
        elapsed_seconds=time.monotonic()-started,sources={str(p):sha(p) for p in paths},release_ready=False,
        scope=__doc__+' Compares all final DSP registers and DP except F2/F3 MMIO shadows. '
        'Appended storage is checked through actual DSP effects. Not waveform, startup phase, '
        'CPU register ABI, game cadence or hardware acceptance.')
    out.mkdir(); (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('sources','continuous','mismatches')}))
    if not passed: raise ValueError('Restart volume state/timer gate failed')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','parent','fixture','out'): p.add_argument('--'+name,type=Path,required=True)
    check(**vars(p.parse_args()))
