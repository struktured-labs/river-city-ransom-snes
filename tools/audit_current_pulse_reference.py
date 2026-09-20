"""Compare eight current-engine pulse-2 reset cases with executed NES controls.

Native audio and fixed callback windows. No phase, gain, rate or onset fitting.
Measured transient bounds are not a perceptual or physical pop-free verdict.
"""
import argparse
import csv
from html import escape
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from tools.audit_main_display_latency import bound_report
from tools.audit_hardware_replay_gaps import waveform_svg
from tools.audit_nes_filter import reconstruct
from tools.audit_retrigger_transient import evaluate, _longest_run
from tools.benchmark_report import sha
from tools.check_nes_disabled_reload import pulse_periodicity
from tools.review_native_transient_stems import same_core_load


def measure(pcm,rate,rows,case):
    a,b=rows[case['first_frame']-1]['start_sample'],rows[case['last_frame']-1]['end_sample']
    block=pcm[a:b].astype(np.int32)
    peak=int(np.abs(block).max())
    if not peak:raise ValueError('Silent pulse case')
    events=[]
    for frame in case['reset_frames']:
        row=rows[frame-1];lo,hi=row['start_sample'],row['end_sample']
        step=int(np.abs(np.diff(pcm[lo-1:hi].astype(np.int32),axis=0)).max())
        quiet=max(_longest_run(np.abs(pcm[lo:hi,ch].astype(np.int32))<32)*1000/rate for ch in (0,1))
        events.append(dict(frame=frame,first=lo,last=hi,max_step=step,
            max_step_to_signal_peak=step/peak,max_step_to_full_scale=step/32768,
            longest_near_zero_ms=quiet))
    lo,hi=rows[case['first_frame']+10]['start_sample'],rows[case['first_frame']+30]['end_sample']
    steady=pcm[lo:hi].astype(np.float64)
    hz=1789773/(16*(case['period']+1))
    return dict(first=a,last=b,peak=peak,events=events,
        max_step_to_signal_peak=max(e['max_step_to_signal_peak'] for e in events),
        max_step_to_full_scale=max(e['max_step_to_full_scale'] for e in events),
        longest_near_zero_ms=max(e['longest_near_zero_ms'] for e in events),
        clipped_fraction=float(np.mean(np.abs(block)>=32767)),
        steady_mean=steady.mean(axis=0).tolist(),steady_ac_rms=steady.std(axis=0).tolist(),
        steady_window=dict(first=lo,last=hi),fundamental=pulse_periodicity(steady,rate,hz))


def audit(fixture,nes,nes_control,nes_observed,nes_control_observed,snes,snes_control,
          snes_observed,snes_control_observed,out):
    if out.exists():raise ValueError('Fresh output required')
    specs={name:bound_report(fixture/name/'manifest.json') for name in
           ('nes-reset','nes-suppressed','snes-reset','snes-suppressed')}
    cases=specs['nes-reset']['cases']
    if any(s['cases']!=cases for s in specs.values()):raise ValueError('Different stimulus cases')
    paths=[Path(__file__),Path('tools/audit_retrigger_transient.py'),Path('tools/audit_nes_filter.py'),
           Path('tools/audit_hardware_replay_gaps.py'),
           Path('tools/check_nes_disabled_reload.py'),Path('tools/review_native_transient_stems.py'),
           Path('tools/build_current_pulse_reference.py')]
    paths += [fixture/name/'manifest.json' for name in specs]
    filter_samples={}
    for normal,observed,variant in ((nes,nes_observed,'reset'),(nes_control,nes_control_observed,'suppressed')):
        base=bound_report(normal/'report.json'); obs=bound_report(observed/'report.json')
        core_a={k:v for k,v in base['sources'].items() if k.endswith('.so')}
        core_b={k:v for k,v in obs['sources'].items() if k.endswith('.so')}
        if len(core_a)!=1 or core_a!=core_b:raise ValueError('Need actual same-core NES control')
        if base['sources'].get(str(fixture/('nes-'+variant)/'manifest.json'))!=sha(fixture/('nes-'+variant)/'manifest.json'):
            raise ValueError('Different NES fixture')
        for filename in ('audio.wav','timeline.json','memory.ram'):
            if sha(normal/filename)!=sha(observed/filename):raise ValueError('NES observer changed execution')
        rate,pcm=wavfile.read(observed/'audio.wav')
        raw=np.fromfile(obs['traces']['samples'],'<i4').reshape(-1,2)
        with Path(obs['traces']['blocks']).open() as stream:blocks=list(csv.reader(stream))
        filter_samples[variant]=reconstruct(raw,blocks,pcm,rate)
        paths += [normal/'report.json',observed/'report.json',Path(obs['traces']['samples']),Path(obs['traces']['blocks'])]
    onsets={}
    for name,normal,observed in (('reset',snes,snes_observed),('suppressed',snes_control,snes_control_observed)):
        result,_,_,_=same_core_load(observed,normal,fixture/('snes-'+name))
        actual=[e['packet'] for e in result['events'] if e['voice']==1]
        expected=sorted(f for c in cases for f in ([c['first_frame']]+(c['reset_frames'] if name=='reset' else [])))
        if (actual!=expected or result['wrong_first_pitch'] or result['stale_nonzero_onsets'] or
                any(e['voice']!=1 for e in result['events'])):
            raise ValueError('Current pulse-2 reset/first-pitch schedule differs')
        onsets[name]=result
        paths += [normal/'report.json',observed/'onset-observer.json',observed/'report.json']
    loaded={}
    for name,root in (('nes',nes),('nes-control',nes_control),('snes',snes),('snes-control',snes_control)):
        rate,pcm=wavfile.read(root/'audio.wav');rows=json.loads((root/'timeline.json').read_text())
        if rate!=(48000 if name.startswith('nes') else 32040) or pcm.dtype!=np.int16 or pcm.shape[1:]!=(2,):
            raise ValueError('Wrong native PCM format')
        loaded[name]=(rate,pcm,rows)
        paths += [root/'audio.wav',root/'timeline.json']
    # Both variants must be identical until the first deliberate periodic reset.
    first=cases[0]['reset_frames'][0]
    if loaded['nes'][2] != loaded['nes-control'][2]:
        raise ValueError('Same-cycle NES control changed frame/sample/write-count/status timeline')
    for system in ('nes','snes'):
        _,a,ar=loaded[system];_,b,br=loaded[system+'-control']
        end=min(ar[first-1]['start_sample'],br[first-1]['start_sample'])
        if not np.array_equal(a[:end],b[:end]) or np.array_equal(a,b):
            raise ValueError('Control differs before reset or has no executed waveform effect')
    out.mkdir(parents=True)
    measurements=[];cards=[];clips=[]
    for i,case in enumerate(cases):
        results={name:measure(pcm,rate,rows,case) for name,(rate,pcm,rows) in loaded.items()}
        gates,limits=evaluate(results['nes'],results['snes'])
        if not all(r['fundamental']['passed'] for r in results.values()):
            raise ValueError('One profile has wrong/missing fundamental')
        entry=dict(case=case,measurements=results,gates=gates,limits=limits,
            passed=all(g['passed'] for g in gates))
        measurements.append(entry)
        cards.append(f'<section><h2>Period ${case["period"]:04X}, duty {case["duty"]}</h2><p>Existing transient bounds: {entry["passed"]}. These are not subjective or physical pass/fail judgments.</p>')
        panels=[]
        for name in ('nes','snes'):
            rate,pcm,rows=loaded[name]
            center=rows[case['reset_frames'][0]-1]['start_sample']/rate
            panels.append((name+' — first reset callback start (not exact APU-write time)',pcm,rate,32768,center))
        graph=f'case-{i}-reset.svg'
        (out/graph).write_text(waveform_svg(panels,limit=.25))
        cards.append(f'<img style="width:100%" src="{graph}" loading="lazy">')
        for name,(rate,pcm,rows) in loaded.items():
            first_sample,last=results[name]['first'],results[name]['last']
            filename=f'case-{i}-{name}.wav'
            wavfile.write(out/filename,rate,pcm[first_sample:last])
            clips.append(dict(file=filename,source=str((dict(nes=nes,snes=snes,**{'nes-control':nes_control,'snes-control':snes_control})[name])/'audio.wav'),first=first_sample,last=last,rate=rate))
            cards.append(f'<p>{name}: native {rate}Hz</p><audio controls preload="none" src="{filename}"></audio>')
        cards.append('<details><summary>Bounds, DC offsets, tone and event measurements</summary><pre>'+escape(json.dumps(entry,indent=2))+'</pre></details></section>')
    # Apply the unchanged numerical checker to a deliberately introduced click
    # and dropout in the actual current-engine PCM, not a fabricated good tone.
    c=cases[0];rate,original,rows=loaded['snes'];at=rows[c['reset_frames'][0]-1]['start_sample']+10
    controls={}
    for name in ('spike','dropout'):
        bad=original.copy()
        if name=='spike':bad[at:at+2]=[[-32768,-32768],[32767,32767]]
        else:bad[at:at+round(rate*.001)]=0
        result=measure(bad,rate,rows,c);gates,_=evaluate(measurements[0]['measurements']['nes'],result)
        controls[name]=not all(g['passed'] for g in gates)
    if not all(controls.values()):raise ValueError('Transient mutation not detected')
    summary={name:dict(restarts=r['restarts'],eligible=r['eligible'],wrong_first_pitch=r['wrong_first_pitch'],
        stale_nonzero_onsets=r['stale_nonzero_onsets'],received_packets=r['received_packets']) for name,r in onsets.items()}
    page='<!doctype html><meta charset="utf-8"><title>Current pulse restart reference</title><style>body{max-width:1100px;margin:30px auto;background:#101821;color:#eee;font:17px system-ui}a{color:#9df}audio{width:100%;max-width:650px}pre{white-space:pre-wrap}section{border-top:1px solid #567;margin:25px 0}</style>'
    page+='<h1>Current pulse-2 restarts versus NES</h1><p>'+escape(__doc__)+'</p>'
    page+='<p>Exact current engine; 8 held tones, 24 periodic resets, all four duty settings at two pitches. Period $06C6/duty3 comes from the retained game transient context. Controls suppress only periodic resets, not initial notes. Native audio is not normalized. NES filter input/output is observed, not bypassed.</p>'
    page+='<pre>'+escape(json.dumps(summary,indent=2))+'</pre>'+''.join(cards)
    page+='<p><a href="report.json">All measurements and source bindings</a></p>'
    (out/'index.html').write_text(page)
    report=dict(scope=__doc__,cases=measurements,snes_onsets=summary,controls=controls,clips=clips,
        nes_control_timeline_identical=True,nes_filter_samples_reconstructed=filter_samples,
        all_transient_bounds_passed=all(c['passed'] for c in measurements),pop_free_verified=False,release_ready=False,
        sources={str(p):sha(p) for p in paths},artifacts={p.name:sha(p) for p in out.iterdir()})
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(cases=[dict(period=c['case']['period'],duty=c['case']['duty'],passed=c['passed'],gates=c['gates']) for c in measurements],onsets=summary,controls=controls)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('fixture','nes','nes-control','nes-observed','nes-control-observed','snes','snes-control',
                 'snes-observed','snes-control-observed','out'):
        p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
