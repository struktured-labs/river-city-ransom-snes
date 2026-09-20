"""Bind cycle-balanced SPC equivalence and unchanged complete game video/RAM."""
import argparse
import hashlib
import json
from pathlib import Path

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha,verify_capture
from tools.build_balanced_pitch_trial import patch
from tools.check_inline_pitch_trial import run
from tools.check_pitch_pair_trial import run_cases
from tools.check_receiver_poll_trial import stream


def check(parent,trial,core,normal_parent,normal_trial,out):
    bound_report(trial/'report.json')
    manifest=json.loads((parent/'manifest.json').read_text());layout=manifest['sweep_driver_layout']
    engines=[(trial/name/'engine.bin').read_bytes() for name in ('baseline','trial')]
    rebuilt,metadata=patch(engines[0],layout)
    if rebuilt!=engines[1] or hashlib.sha256(engines[0]).hexdigest()!=manifest['spc_sha256']:
        raise ValueError('Different parent/patched engine')
    before=run(core,engines[0],layout);after=run(core,engines[1],layout)
    state_errors=[i for i,(a,b) in enumerate(zip(before,after)) if a[0]!=b[0]]
    costs=sorted(set(b[1]-a[1] for a,b in zip(before,after)))
    wrong=bytearray(engines[1])
    for change in metadata['changes']:
        at=change['offset']+len(bytes.fromhex(change['after']))-2
        if wrong[at:at+2]!=bytes.fromhex('d8f3'):raise ValueError('Wrong high mutation site')
        wrong[at]=0xc4
    a=run_cases(core,engines[0],layout);b=run_cases(core,bytes(wrong),layout)
    rejected=sum(x[0]!=y[0] for x,y in zip(a,b))
    continuous={name:[stream(core,engine,layout,mode,delay) for mode in (0,128)
        for delay in (0,256,512,2048)] for name,engine in zip(('baseline','trial'),engines)}
    base,rows=verify_capture(normal_parent);candidate,changed=verify_capture(normal_trial)
    if (not base['capture_complete'] or not candidate['capture_complete'] or
        base['rom_sha256']!=sha(parent/'native-cpu.sfc') or
        candidate['rom_sha256']!=sha(trial/'game/native-cpu.sfc') or
        base['scenario_sha256']!=candidate['scenario_sha256'] or len(rows)!=len(changed)):
        raise ValueError('Incomplete or different game route')
    # Only audio *content* is allowed to change, not its sample count or callback timing.
    errors=[];audio_changed=0
    for a,b in zip(rows,changed):
        keys=(set(a)|set(b)) - {'audio'}
        different=[k for k in keys if a.get(k)!=b.get(k)]
        if a['audio']['samples']!=b['audio']['samples']:different.append('audio.samples')
        if different:errors.append(dict(frame=a['frame'],fields=different))
        audio_changed+=a['audio']!=b['audio']
    passed=not state_errors and costs==[0] and rejected>0 and not errors and all(
        r['passed'] and not r['bad_volume_writes'] for side in continuous.values() for r in side)
    sources=[Path(__file__),Path('tools/build_balanced_pitch_trial.py'),Path('tools/build_inline_pitch_trial.py'),
        Path('tools/check_inline_pitch_trial.py'),Path('tools/check_pitch_pair_trial.py'),Path('tools/check_receiver_poll_trial.py'),
        Path('tools/check_sweep_driver.py'),Path('tools/spc_sweep_driver_probe.inc'),core,
        parent/'manifest.json',parent/'native-cpu.sfc',trial/'report.json',trial/'baseline/engine.bin',
        trial/'trial/engine.bin',normal_parent/'capture.json',normal_trial/'capture.json']
    sources.extend(core.parent.parent/'apu/bapu/smp'/name for name in ('core.cpp','smp.cpp','memory.cpp','timing.cpp'))
    report=dict(passed=passed,cases=len(before),state_errors=state_errors,added_spc_clocks=costs,
        wrong_high_mutant_failures=rejected,continuous=continuous,game_frames=len(rows),
        nonaudio_timeline_errors=errors,audio_metric_changed_frames=audio_changed,
        sources={str(p):sha(p) for p in sources},
        scope='Same 50,265 state cases, exact actual SPC call cost, continuous-clock delayed-transfer cases. '
        'Every complete game timeline field except audio content must equal parent, including all video/RAM '
        'hashes, sample counts, inputs, NMI and native state. Does not prove every caller/input/physical '
        'path, perceptual benefit or pop-free audio.')
    out.mkdir(parents=True,exist_ok=False);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('passed','cases','state_errors','added_spc_clocks',
        'wrong_high_mutant_failures','game_frames','nonaudio_timeline_errors','audio_metric_changed_frames')}))
    if not passed:raise ValueError('Balanced pitch state/timing/game regression')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','trial','core','normal-parent','normal-trial','out'):p.add_argument('--'+name,type=Path,required=True)
    check(**vars(p.parse_args()))
