"""Measure intentional NES zero-write suppression without gain/time fitting."""
import argparse
import csv
import html
import json
from pathlib import Path
import shutil

import numpy as np
from scipy.io import wavfile

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha,verify_capture
from tools.capture_nes_volume_sensitivity import nonaudio,validate_log
from tools.frame_audit import verify_frame


def compare_pcm(before,after):
    if (before.dtype!=np.int16 or after.dtype!=np.int16 or before.shape!=after.shape or
        before.ndim!=2 or before.shape[1]!=2 or len(before)<2):
        raise ValueError('Need equal native stereo S16 sample arrays')
    a=before.astype(np.int32);b=after.astype(np.int32);delta=b-a
    return dict(sample_frames=len(a),changed_sample_frames=int(np.count_nonzero(np.any(delta,axis=1))),
        max_absolute_difference=int(np.abs(delta).max()),rms_difference=float(np.sqrt(np.mean(delta.astype(float)**2))),
        baseline_peak=int(np.abs(a).max()),suppressed_peak=int(np.abs(b).max()),
        baseline_max_step=int(np.abs(np.diff(a,axis=0)).max()),
        suppressed_max_step=int(np.abs(np.diff(b,axis=0)).max()),
        baseline_clipped_samples=int(np.count_nonzero(np.abs(a)>=32767)),
        suppressed_clipped_samples=int(np.count_nonzero(np.abs(b)>=32767)))


def review(plan,normal,mutant,out):
    if out.exists():raise ValueError('Fresh review required')
    planned=bound_report(plan/'report.json');reports=[bound_report(p/'volume-sensitivity.json') for p in (normal,mutant)]
    if reports[0]['suppressed'] or not reports[1]['suppressed'] or reports[1]['normal']!=str(normal):
        raise ValueError('Need explicit original and intentional-mutation arms')
    sources={**planned['sources']}
    for r in reports:
        sources.update(r['sources'])
        if not all(r[k] for k in ('cpu_write_intent_identical','exact_pc_clocks_identical','nonaudio_and_sample_timing_identical')):
            raise ValueError('Mutation changed more than selected APU dispatches')
    captures=[verify_capture(p) for p in (normal,mutant)]
    a,b=(r for _,r in captures)
    if nonaudio(a)!=nonaudio(b) or captures[0][0]['core_sha256']!=captures[1][0]['core_sha256']:
        raise ValueError('Not same-core identical game execution and sample lattice')
    for name in ('events','writes'):
        if sha(Path(reports[0]['traces'][name]))!=sha(Path(reports[1]['traces'][name])):
            raise ValueError('CPU clock or original write intent changed')
    with Path(reports[1]['traces']['suppressed']).open() as f:
        executed=validate_log(list(csv.reader(f)),planned['drops'])
    rate,original=wavfile.read(normal/'audio.wav');mr,changed=wavfile.read(mutant/'audio.wav')
    if rate!=48000 or mr!=rate:raise ValueError('Different native NES sample rate')
    whole=compare_pcm(original,changed)
    if not whole['changed_sample_frames']:raise ValueError('Executed mutation made no measured PCM difference')
    windows=[]
    for index,c in enumerate(planned['selected']):
        first=max(1,c['zeros'][0]['frame']-1);last=min(len(a),c['final']['frame']+1)
        start=a[first-1]['audio_start_sample'];end=a[last-1]['audio_start_sample']+a[last-1]['audio']['samples']
        overlap=[i for i,x in enumerate(planned['selected'])
                 if x['zeros'][0]['frame']<=last and x['final']['frame']>=first]
        windows.append(dict(index=index,driver=c['driver'],register=c['register'],
            duration_cycles=c['duration_cycles'],first_frame=first,last_frame=last,
            first_sample=start,last_sample=end,overlapping_selected_runs=overlap,
            measurements=compare_pcm(original[start:end],changed[start:end])))
    ordered=sorted(range(len(windows)),key=lambda i:(windows[i]['duration_cycles'],i))
    strongest=max(range(len(windows)),key=lambda i:windows[i]['measurements']['max_absolute_difference'])
    chosen=[('shortest_interval',ordered[0]),('median_interval',ordered[len(ordered)//2]),
            ('longest_interval',ordered[-1]),('largest_native_difference',strongest)]
    out.mkdir(parents=True);clips=[];cards=[]
    for reason,index in chosen:
        c=planned['selected'][index];frame=c['zeros'][0]['frame']
        first=max(1,frame-15);last=min(len(a),c['final']['frame']+15)
        start=a[first-1]['audio_start_sample'];end=a[last-1]['audio_start_sample']+a[last-1]['audio']['samples']
        picture=verify_frame(normal,a[frame-1]);mutant_picture=verify_frame(mutant,b[frame-1])
        if sha(picture)!=sha(mutant_picture):raise ValueError('Selected game image differs')
        name=reason+'.png';shutil.copyfile(picture,out/name)
        sources[str(picture)]=sha(picture);sources[str(mutant_picture)]=sha(mutant_picture)
        card='<section><h2>'+html.escape(reason.replace('_',' '))+f' · frame{frame}</h2><img src="{name}">'
        for label,data,path in (('original',original,normal),('suppressed',changed,mutant)):
            filename=reason+'-'+label+'.wav';wavfile.write(out/filename,rate,data[start:end])
            clips.append(dict(file=filename,source=str(path/'audio.wav'),first=start,last=end,rate=rate))
            card+=f'<p>{label}<br><audio controls src="{filename}"></audio></p>'
        card+='<pre>'+html.escape(json.dumps(windows[index],indent=2))+'</pre></section>';cards.append(card)
    for p in (Path(__file__),Path('tools/capture_nes_volume_sensitivity.py'),
        Path('tools/plan_nes_volume_suppression.py'),Path('tests/test_nes_volume_measurement.py'),
        plan/'report.json',normal/'volume-sensitivity.json',mutant/'volume-sensitivity.json'):
        sources[str(p)]=sha(p)
    result=dict(executed_suppressed_writes=executed,selected_runs=len(planned['selected']),
        excluded_runs=len(planned['excluded']),frames=len(a),whole_pcm=whole,windows=windows,
        windows_with_difference=sum(bool(w['measurements']['changed_sample_frames']) for w in windows),
        chosen=chosen,clips=clips,sources=sources,
        cpu_timing_input_ram_video_unchanged=True,final_write_intent_and_reloads_unchanged=True,
        normal_reproduces_original=True,mutation_audio_is_original_reference=False,
        physical_pop_causality_proven=False,perceptual_verdict=False,release_ready=False,
        scope=__doc__+' This is a limited causal experiment on an NES emulator, not the SNES port '
        'or a complete snapshot-protocol simulation. Only selected same-mode constant-volume zero '
        'runs with a preceding nonzero volume are omitted. All final writes/reloads remain at '
        'their original clocks. Frame-bound windows may overlap other selected runs and contain '
        'filter tails; they are not independent per-write effects. No subjective audibility verdict.')
    page='<!doctype html><meta charset="utf-8"><title>NES intermediate-volume sensitivity</title><style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:2em auto}a{color:cyan}img{width:384px;image-rendering:pixelated}pre{white-space:pre-wrap}section{border-top:1px solid #456;margin-top:2em}</style>'
    page+='<h1>NES intermediate-volume sensitivity — intentional mutation</h1><p>'+html.escape(result['scope'])+'</p>'
    page+=f'<p>{executed} exact zero-volume dispatches omitted across{len(windows)} runs. '
    page+=f'All{len(a):,} game frames, CPU write intents and exact-PC clocks remain identical. '
    page+='The unmodified same-core control reproduces the original NES PCM exactly.</p>'
    page+='<h2>Whole native PCM</h2><pre>'+html.escape(json.dumps(whole,indent=2))+'</pre>'
    page+='<p>Native clips use identical absolute sample bounds, no gain or phase/time alignment. '
    page+='Images are identical game-state context, not evidence that audio matches. '
    page+='The first three selections are based on source intervals; the fourth deliberately shows the largest measured difference.</p>'
    page+='<p><a href="report.json">Every selected window, overlap and evidence hash</a></p>'+''.join(cards)
    (out/'index.html').write_text(page);result['artifacts']={p.name:sha(p) for p in out.iterdir()}
    for p,h in sources.items():
        if sha(Path(p))!=h:raise ValueError('Changed source: '+p)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('executed_suppressed_writes','selected_runs','frames','whole_pcm','windows_with_difference')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('plan','normal','mutant','out'):p.add_argument('--'+name,type=Path,required=True)
    review(**vars(p.parse_args()))
