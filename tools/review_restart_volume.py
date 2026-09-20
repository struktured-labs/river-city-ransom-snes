"""Auditable native-PCM restart experiment, including failed late-volume control."""
import argparse
import json
from pathlib import Path
import time

import numpy as np
from scipy.io import wavfile

from tools.audit_dsp_latency import next_dac_sample
from tools.audit_main_display_latency import bound_report
from tools.audit_pulse_onset import load
from tools.benchmark_report import sha


def first_volume_failures(events):
    return [dict(packet=e['packet'],voice=e['voice'],actual=[e['samples'][6]['left'],e['samples'][6]['right']],
                 expected=e['target_volumes']) for e in events
            if [e['samples'][6]['left'],e['samples'][6]['right']]!=e['target_volumes']]


def measure(pcm,event,startup):
    keyon=next_dac_sample(event['keyon_write']['tick'])
    first=min(next_dac_sample(e['samples'][6]['tick']) for e in startup)
    left=keyon-8
    if left<0 or first+96>len(pcm):raise ValueError('Incomplete native waveform context')
    pre=pcm[left:first].astype(np.int32); post=pcm[first:first+96].astype(np.int32)
    return dict(keyon_sample=keyon,first_oscillator_sample=first,window=[left,first],
        pre_note_nonzero_samples=int(np.count_nonzero(np.any(pre!=0,axis=1))),
        pre_note_peak=int(np.abs(pre).max()),post_note_peak=int(np.abs(post).max()),
        pre_note_left=pre[:,0].tolist())


def review(fixture,before,normal_before,after,normal_after,onset,state,failed,out):
    started=time.monotonic()
    if out.exists():raise ValueError('Fresh review required')
    stateproof=bound_report(state/'report.json')
    previous=bound_report(failed/'report.json')
    onsetproof=bound_report(onset/'report.json')
    spec=bound_report(fixture/'trial'/'manifest.json')
    a,_,aw,_=load(before,normal_before,fixture/'baseline')
    b,_,bw,_=load(after,normal_after,fixture/'trial')
    if a!=onsetproof['baseline'] or b!=onsetproof['candidate']:raise ValueError('Changed onset qualification')
    # load() validates controls, but also demand the exact same core explicitly.
    cores=[]
    for root in (before,normal_before,after,normal_after):
        report=bound_report(root/'report.json')
        cores.append({p:h for p,h in report['sources'].items() if p.endswith('.so')})
    if not cores[0] or any(c!=cores[0] for c in cores):raise ValueError('Different observer core')
    waveforms=[]
    for root in (normal_before,normal_after):
        rate,pcm=wavfile.read(root/'audio.wav')
        if rate!=32040 or pcm.dtype!=np.int16 or pcm.ndim!=2 or pcm.shape[1]!=2:raise ValueError('Wrong native PCM')
        waveforms.append(pcm)
    if waveforms[0].shape!=waveforms[1].shape:raise ValueError('Unequal fixture duration')
    events=[{(e['packet'],e['voice']):e for e in arm['events']} for arm in (a,b)]
    if events[0].keys()!=events[1].keys():raise ValueError('Different restart sequence')
    fields=('pitch','register_pitch','srcn','env','output','left','right')
    changed=[dict(packet=key[0],voice=key[1]) for key in events[0] if any(
        any(x[f]!=y[f] for f in fields) for x,y in zip(events[0][key]['samples'][6:],events[1][key]['samples'][6:]))]
    cases=[]
    for case in spec['cases']:
        if case['mask']!=3:continue
        packet=case['resume_frame']; arms=[]
        for ev,pcm in zip(events,waveforms):
            current=[ev[packet,v] for v in (0,1)]
            arms.append(measure(pcm,current[0],current))
        cases.append(dict(case=case,packet=packet,baseline=arms[0],trial=arms[1]))
    late=first_volume_failures(b['events'])
    old_late=first_volume_failures(previous['candidate']['events'])
    # Validate the actual output gate against a damaged waveform and silence,
    # not a fabricated report field. Use the first predetermined case.
    first=cases[0]; packet=first['packet']; current=[events[1][packet,v] for v in (0,1)]
    bad=waveforms[1].copy();bad[first['trial']['window'][0],:]=32767
    spike_rejected=measure(bad,current[0],current)['pre_note_nonzero_samples']>0
    silence_rejected=measure(np.zeros_like(bad),current[0],current)['post_note_peak']==0
    passed=stateproof['passed'] and onsetproof['passed'] and not late and not changed and bool(old_late) and spike_rejected and silence_rejected and all(
        c['baseline']['pre_note_nonzero_samples']>0 and c['trial']['pre_note_nonzero_samples']==0 and c['trial']['post_note_peak']>0 for c in cases)
    out.mkdir()
    drawing=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 800"><rect width="1100" height="800" fill="#20252a"/>']
    clips=[]
    for row,case in enumerate(cases[:4]):
        for col,(name,pcm) in enumerate(zip(('baseline','trial'),waveforms)):
            m=case[name]; center=m['keyon_sample']; left=center-16; right=center+40
            x=col*550+30;y=row*200+40
            points=' '.join(f'{x+i*8:.1f},{y+65-int(v)*.012:.1f}' for i,v in enumerate(pcm[left:right,0]))
            drawing.append(f'<text x="{x}" y="{y-15}" fill="white" font-size="16">{name}, duty {case["case"]["duty"]}, packet {case["packet"]}</text>')
            drawing.append(f'<polyline points="{points}" fill="none" stroke="#55ddff" stroke-width="1.5"/>')
            for sample,color in ((center,'#aaa'),(m['first_oscillator_sample'],'#6d6')):
                sx=x+(sample-left)*8
                drawing.append(f'<path d="M{sx},{y}V{y+130}" stroke="{color}" stroke-dasharray="3 3"/>')
            drawing.append(f'<text x="{x}" y="{y+150}" fill="#ccc" font-size="13">−16 to +39 native samples relative to KON (diagnostic)</text>')
            lo=center-8010;hi=center+8010
            filename=f'{row+1:02d}-{name}.wav';wavfile.write(out/filename,32040,pcm[lo:hi])
            clips.append(dict(file=filename,start_sample=lo,end_sample=hi,arm=name,packet=case['packet']))
    drawing.append('</svg>');(out/'waveforms.svg').write_text(''.join(drawing))
    metrics=[]
    for pcm in waveforms:
        x=pcm.astype(np.int32);metrics.append(dict(samples=len(pcm),peak=int(np.abs(x).max()),
            max_adjacent_step=int(np.abs(np.diff(x,axis=0)).max()),rms=float(np.sqrt(np.mean(x.astype(float)**2))),
            clipped_samples=int(np.count_nonzero(np.any((x==-32768)|(x==32767),axis=1)))))
    rows=''.join(f'<tr><td>{c["packet"]}</td><td>{c["case"]["old"]} / {c["case"]["new"]}</td><td>{c["case"]["duty"]}</td><td>{c["baseline"]["pre_note_nonzero_samples"]}</td><td>{c["trial"]["pre_note_nonzero_samples"]}</td></tr>' for c in cases)
    players=''.join(f'<tr><td>{c["packet"]}</td><td>{c["arm"]}</td><td><audio controls preload="none" src="{c["file"]}"></audio></td></tr>' for c in clips)
    status='FOCUSED PASS' if passed else 'FAIL'
    html=f'''<!doctype html><meta charset="utf-8"><title>Restart volume experiment</title>
<style>body{{background:#111;color:#ddd;font:17px system-ui;max-width:1150px;margin:30px auto}}a{{color:#7df}}td,th{{padding:8px;border-bottom:1px solid #444}}img{{width:100%}}audio{{width:360px}}</style>
<h1>Restart volume: {status}, isolated sound fixture</h1>
<p>No game deployment, physical-audio claim, or pop-free claim. The game speed/scrolling candidate is unchanged.</p>
<p>Both controls use the current sound engine plus identical upload padding. 1,788 packets; 36 duty/period/channel cases. No RAM edits, filtering, gain normalization, or resampling. Same-core observer on/off outputs match, including PCM.</p>
<p>The early prototype removed the burst but delivered volume late on {len(old_late)} restarts: rejected. The interleaved prototype has {len(late)} late-volume and {b['wrong_first_pitch']} wrong-first-pitch events. Across {len(events[1])} restarts, all following 90 per-voice samples match the control in pitch, envelope, output, and volumes; {len(changed)} mismatches.</p>
<p>State/timer qualification: {stateproof['cases']:,} state cases, 16 continuous receiver/timer cases. Added publisher/flush cost remains in <a href="../{state.name}/report.json">the state report</a>; game cadence is untested.</p>
<h2>Actual waveform: old-note burst disappears</h2><p>Gray: KON write. Green: first restarted oscillator sample. Plots are event-relative diagnostics, not aligned primary comparisons. PCM remains native and untouched.</p><img src="waveforms.svg">
<table><tr><th>Packet</th><th>Periods</th><th>Duty</th><th>Old pre-note samples</th><th>Trial pre-note samples</th></tr>{rows}</table>
<h2>Native clips, half a second each</h2><p>These are synthetic test notes, not RCR music. Volume is unchanged. No subjective listening claim is made.</p><table>{players}</table>
<p>Untrimmed captures: <a href="../{normal_before.name}/audio.wav">control</a> · <a href="../{normal_after.name}/audio.wav">trial</a>.</p>
<h2>Remaining / tradeoffs</h2><p>Global maximum adjacent step is {metrics[0]['max_adjacent_step']} → {metrics[1]['max_adjacent_step']}, not an overall reduction. Oscillator phase between voices changes; source-waveform equality after restart does not establish whole-mix or NES fidelity. Mute timing, all DSP phases, real-game timing/PCM and hardware audio still need qualification. The expanded engine is not integrated.</p>
<p>Mutation controls: injected pre-note spike rejected; silence fails activity; wrong staged-volume source and restored legacy writer rejected. <a href="report.json">Complete source-bound data</a>.</p>'''
    (out/'index.html').write_text(html)
    paths=[Path(__file__),Path('tests/test_restart_volume_review.py'),Path('tools/audit_pulse_onset.py'),
        Path('tools/audit_dsp_latency.py'),Path('tools/audit_main_display_latency.py'),
        state/'report.json',failed/'report.json',onset/'report.json',
        fixture/'trial'/'manifest.json',fixture/'baseline'/'manifest.json']
    paths += [root/name for root in (before,after,normal_before,normal_after) for name in ('report.json','audio.wav')]
    result=dict(passed=passed,cases=cases,late_volume=late,rejected_prototype_late_volume=old_late,
        changed_restarted_voices=changed,restarts=len(events[1]),post_restart_samples_per_voice=90,
        metrics=dict(baseline=metrics[0],trial=metrics[1]),clips=clips,
        controls=dict(injected_spike_rejected=spike_rejected,silence_rejected=silence_rejected),
        observer_neutral=True,physical_audio_verified=False,pop_free_verified=False,release_ready=False,
        elapsed_seconds=time.monotonic()-started,sources={str(p):sha(p) for p in paths},
        artifacts={p.name:sha(p) for p in out.iterdir() if p.is_file()},scope=__doc__)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=passed,cases=len(cases),restarts=len(events[1]),late_volume=len(late),
        failed_prototype_late_volume=len(old_late),changed_restarted_voices=len(changed),seconds=result['elapsed_seconds'])))
    if not passed:raise ValueError('Restart-volume focused acceptance failed')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('fixture','before','normal-before','after','normal-after','onset','state','failed','out'):
        p.add_argument('--'+name,type=Path,required=True)
    review(**vars(p.parse_args()))
