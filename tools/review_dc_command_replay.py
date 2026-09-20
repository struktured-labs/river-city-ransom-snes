"""Reject or retain the pulse trial using unchanged physical-event windows.

Large sample steps are diagnostic observations, not automatically audible pops.
No new physical recording, local alignment, gain fit or sample-rate conversion.
"""
import argparse
from html import escape
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from tools.audit_dc_pulse_trial import dsp_equal
from tools.audit_hardware_replay_gaps import waveform_svg
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_dc_packet_replay import replace
from tools.review_native_transient_stems import composition, read, same_core_load, steps_at_peak


def compare_window(before,after,first,last):
    a=steps_at_peak(dict(replay=before,trial=after),first,last)
    b=steps_at_peak(dict(replay=after,parent=before),first,last)
    old=a['channels_at_identical_sample']['replay']['window_max_step']
    new=a['channels_at_identical_sample']['trial']['window_max_step']
    if not old:raise ValueError('Silent parent window')
    return dict(parent_max_step=old,trial_max_step=new,ratio=new/old,
        grows_over_one_percent=new>old*1.01,parent_peak=a,trial_peak=b)


def review(out):
    if out.exists():raise ValueError('Fresh output required')
    root=Path('build');sources={}
    def bind(p):sources[str(p)]=sha(p)
    def report(p):
        r=bound_report(p);sources.update(r.get('sources',{}));bind(p);return r
    prior=report(root/'native-transient-stems-2290/report.json')
    qualification=report(root/'dc-pulse-review-2340/report.json')
    if not qualification['passed']:raise ValueError('Unqualified isolated/full-route trial')
    hardware=report(root/'current-logger-audit-2079/report.json')
    parent=root/'dispatch-command-replay-2277';trial=root/'dc-command-replay-2342'
    normal=root/'dispatch-onset-normal-2280';changed=root/'dc-command-normal-2343'
    observed=root/'dispatch-onset-observed-2281';new_observed=root/'dc-command-observed-2344'
    specs=[report(f/'manifest.json') for f in (parent,trial)]
    stream=b''.join(b'\1'+bytes.fromhex(r['packet']) for r in hardware['log']['records'])
    if any((f/'stream.bin').read_bytes()!=stream for f in (parent,trial)):
        raise ValueError('Commands differ from physical episode')
    meta=json.loads((root/'dc-pulse-trial-2319/manifest.json').read_text())
    rom=root/'dc-pulse-trial-2319/native-cpu.sfc';image=rom.read_bytes()
    at,size=meta['sweep_driver_rom_offset'],meta['sweep_driver_layout']['engine_bytes']
    if (sha(rom)!=meta['rom_sha256'] or specs[1]['engine_source_rom_sha256']!=meta['rom_sha256'] or
            image[at:at+size]!=(trial/'engine.bin').read_bytes()):raise ValueError('Different candidate engine')
    expected,_=replace((parent/'player.sfc').read_bytes(),(parent/'engine.bin').read_bytes(),(trial/'engine.bin').read_bytes())
    if expected!=(trial/'player.sfc').read_bytes():raise ValueError('Unrelated replay changes')
    proofs=[];writes=[];ready=[];cores=[]
    for f,n,o in ((parent,normal,observed),(trial,changed,new_observed)):
        for p in (n/'report.json',o/'report.json',o/'onset-observer.json'):report(p)
        r,_,w,rd=same_core_load(o,n,f)
        if r['wrong_first_pitch'] or r['stale_nonzero_onsets']:raise ValueError('Wrong/stale onset')
        proofs.append({k:r[k] for k in ('observer_neutral','raw_dac_identical','received_packets','eligible','wrong_first_pitch','stale_nonzero_onsets')})
        writes.append(w);ready.append(rd);sources.update(r['sources'])
        receipt=bound_report(n/'report.json');cores.append({k:v for k,v in receipt['sources'].items() if k.endswith('.so')})
        for folder in (f,n,o):
            for name in ('player.sfc','engine.bin','stream.bin','timeline.json','memory.ram','last.png','audio.wav'):
                p=folder/name
                if p.exists():bind(p)
    if cores[0]!=cores[1]:raise ValueError('Different comparison cores')
    dsp=dsp_equal(*writes)
    if ready[0].keys()!=ready[1].keys():raise ValueError('Missing completion')
    for k,a in ready[0].items():
        b=ready[1][k];expected=dict(a);expected['registers']=list(a['registers'])
        for reg in (7,0x17):
            if expected['registers'][reg]==31:expected['registers'][reg]=35
        if expected!=b:raise ValueError('Completion changed outside pulse gain')
    timeline=json.loads((normal/'timeline.json').read_text())
    if timeline!=json.loads((changed/'timeline.json').read_text()):raise ValueError('Replay timing differs')
    arrays=dict(parent=read(normal/'audio.wav',32040),trial=read(changed/'audio.wav',32040))
    stem_bindings={}
    for label,folder,n,mode in (
        ('parent-noise','dc-command-parent-noise-2345',normal,'noise'),
        ('trial-noise','dc-command-trial-noise-2346',changed,'noise'),
        ('parent-rest','dc-command-parent-rest-2347',normal,'without-noise'),
        ('trial-rest','dc-command-trial-rest-2348',changed,'without-noise')):
        f=root/folder;r=report(f/'stem.json')
        if r['mode']!=mode or not all(r['nonaudio_equal'].values()) or r['sources'].get(str(n/'report.json'))!=sha(n/'report.json'):
            raise ValueError('Different stem control')
        arrays[label]=read(f/'audio.wav',32040);bind(f/'audio.wav');stem_bindings[label]=str(f/'audio.wav')
    noise_equal=np.array_equal(arrays['parent-noise'],arrays['trial-noise'])
    if not noise_equal:raise ValueError('Pulse patch altered noise')
    sums={side:composition(arrays[side],arrays[side+'-noise'],arrays[side+'-rest']) for side in ('parent','trial')}
    physical_path=root/'current-logger-decoded-2059/input.wav';physical=read(physical_path,48000)
    if prior['sources'].get(str(physical_path))!=sha(physical_path):raise ValueError('Different physical PCM')
    bind(physical_path)
    out.mkdir(parents=True);events=[];cards=[];clips=[]
    audio_paths=dict(parent=normal/'audio.wav',trial=changed/'audio.wav',**stem_bindings)
    for i,e in enumerate(prior['events']):
        window=e['mapped'];item=dict(physical=e['physical'],mapped=window,classified_as_pop=False)
        card=f'<h2>Physical {e["physical"]["seconds"]:.6f}s</h2>'
        if window['covered']:
            first,last=window['first'],window['last']
            item['comparison']=compare_window(arrays['parent'],arrays['trial'],first,last)
            item['at_parent_peak']=steps_at_peak(dict(replay=arrays['parent'],trial=arrays['trial'],
                noise=arrays['parent-noise'],parent_rest=arrays['parent-rest'],trial_rest=arrays['trial-rest']),first,last)
            card+='<pre>'+escape(json.dumps({k:v for k,v in item['comparison'].items() if k not in ('parent_peak','trial_peak')},indent=2))+'</pre>'
            center=window['center_seconds'];name=f'event-{i:02d}.svg'
            (out/name).write_text(waveform_svg([(side,arrays[side],32040,32768,center) for side in ('parent','trial')],limit=.1))
            card+=f'<img src="{name}" loading="lazy">'
            for label in ('parent','trial','parent-noise'):
                first=max(0,round(center*32040)-16020);last=min(len(arrays[label]),round(center*32040)+16020)
                name=f'event-{i:02d}-{label}.wav';wavfile.write(out/name,32040,arrays[label][first:last])
                clips.append(dict(file=name,source=str(audio_paths[label]),first=first,last=last,rate=32040))
                card+=f'<p>{label}</p><audio controls preload="none" src="{name}"></audio>'
        else:card+='<p>Outside emitted command coverage; retained, not assessed.</p>'
        events.append(item);cards.append(card)
    covered=[e['comparison'] for e in events if e['mapped']['covered']]
    regressed=sum(e['grows_over_one_percent'] for e in covered)
    result=dict(measurement_validated=True,scoped_isolated_gates_passed=True,
        fixed_lag_seconds=prior['fixed_lag_seconds'],events=events,proofs=proofs,dsp=dsp,
        completions=len(ready[0]),noise_pcm_identical=bool(noise_equal),compositions=sums,
        covered_windows=len(covered),windows_growing_over_one_percent=regressed,
        no_window_step_growth_over_one_percent=not regressed,
        promotion_recommended=False,release_ready=False,physical_audio_verified=False,pop_free_verified=False,
        decision='Retain as a rejected pop-fix trial: multiple fixed windows have larger absolute steps. '
                 'No perceptual verdict follows from step size alone; no hardware deployment.',
        scope=__doc__,clips=clips)
    for name in (__file__,'tools/build_dc_packet_replay.py','tools/build_dc_pulse_trial.py',
            'tools/audit_dc_pulse_trial.py','tools/review_native_transient_stems.py',
            'tools/audit_hardware_replay_gaps.py','tools/audit_main_display_latency.py',
            'tools/benchmark_report.py','tests/test_dc_command_replay.py'):bind(Path(name))
    if any(sha(Path(p))!=v for p,v in sources.items()):raise ValueError('Source changed during review')
    result['sources']=sources
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Pulse trial: recorded-command failure</title><style>body{background:#101820;color:#eee;font:17px system-ui;max-width:1100px;margin:30px auto}a{color:#8df}audio,img{width:100%}pre{white-space:pre-wrap}</style><h1>Do not promote: recorded-command pulse trial</h1><p>'+escape(result['decision'])+f'</p><p>{regressed} of {len(covered)} fixed windows grow by more than1%. Noise is unchanged. Same1238 packets, actual DSP clocks and frame/sample schedule. No physical waveform-phase equivalence is claimed.</p><p><a href="report.json">All measurements and hashes</a></p>'+''.join(cards))
    result['artifacts']={p.name:sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('measurement_validated','covered_windows','windows_growing_over_one_percent','dsp','noise_pcm_identical','promotion_recommended')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    review(**vars(p.parse_args()))
