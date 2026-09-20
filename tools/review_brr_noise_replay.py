"""Audit the binary BRR noise prototype without promoting it to the game."""
import argparse
import html
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from tools.audit_main_display_latency import bound_report
from tools.audit_recorded_transients import waveform_svg
from tools.benchmark_report import sha
from tools.build_brr_noise_replay import patch
from tools.review_native_transient_stems import composition, read, same_core_load
from tools.review_noise_packet_reference import measure, validate_timeline


def build(manifest,out):
    if out.exists():raise ValueError('Fresh review required')
    paths={k:Path(v) for k,v in json.loads(manifest.read_text()).items()}
    sources={str(p):sha(p) for p in (manifest,Path(__file__),Path('tools/build_brr_noise_replay.py'),
        Path('tools/audit_main_display_latency.py'),Path('tools/review_native_transient_stems.py'),
        Path('tools/review_noise_packet_reference.py'),Path('tools/audit_recorded_transients.py'))}
    def report(path):
        result=bound_report(path);sources[str(path)]=sha(path);sources.update(result['sources']);return result
    selection=report(paths['selection']/'report.json');quality=report(paths['quality']/'report.json')
    original=report(paths['parent_fixture']/'manifest.json');trial=report(paths['fixture']/'manifest.json')
    expected,detail=patch((paths['parent_fixture']/'engine.bin').read_bytes())
    if expected!=(paths['fixture']/'engine.bin').read_bytes() or detail!=trial['noise_prototype']:
        raise ValueError('Prototype differs from exact guarded noise patch')
    packets=(paths['fixture']/'stream.bin').read_bytes()
    if packets!=(paths['parent_fixture']/'stream.bin').read_bytes():raise ValueError('Changed command stream')
    proofs={};ready={};core_ids=[]
    for label,f,n,o in (('parent','parent_fixture','parent_normal','parent_observed'),
                        ('trial','fixture','normal','observed')):
        proof,_,_,states=same_core_load(paths[o],paths[n],paths[f])
        receipt=report(paths[n]/'report.json')
        core_ids.append({k:v for k,v in receipt['sources'].items() if k.endswith('.so')})
        sources.update(proof['sources']);ready[label]=states
        proofs[label]={k:proof[k] for k in ('observer_neutral','raw_dac_identical','received_packets',
            'eligible','wrong_first_pitch','stale_nonzero_onsets')}
        if proof['wrong_first_pitch'] or proof['stale_nonzero_onsets']:raise ValueError('Pulse onset regression')
    if core_ids[0]!=core_ids[1]:raise ValueError('Cross-engine comparison uses different cores')
    if ready['parent'].keys()!=ready['trial'].keys():raise ValueError('Missing completion')
    nonnoise=[];noise_states=[]
    allowed={0x32,0x33,0x34,0x3d,0x6c}
    for number,state in ready['trial'].items():
        p=packets[(number-1)*24+1:number*24];regs=state['registers']
        target=detail['pitches'][p[14]&15]
        if regs[0x3d]!=0 or regs[0x34]!=5 or regs[0x32]+256*regs[0x33]!=target:
            raise ValueError('Actual DSP did not select the expected BRR source/pitch')
        changes={f'{i:02x}':[a,b] for i,(a,b) in enumerate(zip(ready['parent'][number]['registers'],regs)) if a!=b and i not in allowed}
        if changes:nonnoise.append(dict(packet=number,changes=changes))
        noise_states.append(dict(packet=number,source=regs[0x34],non=regs[0x3d],pitch=target))
    arrays={};rows={}
    for key in ('parent_normal','normal','parent_noise','noise','rest'):
        arrays[key]=read(paths[key]/'audio.wav',32040)
        rows[key]=json.loads((paths[key]/'timeline.json').read_text())
        validate_timeline(rows[key],trial['source_frames'],len(arrays[key]))
        for name in ('audio.wav','timeline.json'):
            p=paths[key]/name;sources[str(p)]=sha(p)
    for key,normal,mode in (('parent_noise','parent_normal','noise'),('noise','normal','noise'),('rest','normal','without-noise')):
        r=report(paths[key]/'stem.json')
        if r['mode']!=mode or not all(r['nonaudio_equal'].values()) or r['sources'].get(str(paths[normal]/'report.json'))!=sha(paths[normal]/'report.json'):
            raise ValueError('Unqualified stem')
    mix=composition(arrays['normal'],arrays['noise'],arrays['rest'])
    timeline_diffs={k:sum(a[k]!=b[k] for a,b in zip(rows['parent_normal'],rows['normal'])) for k in rows['normal'][0]}
    if timeline_diffs['packet'] or timeline_diffs['source_frame'] or timeline_diffs['packets']:
        raise ValueError('Replay command ordering changed')
    out.mkdir(parents=True);events=[];clips=[];cards=[]
    for index,event in enumerate(selection['events'],1):
        if not event['mapped']['covered']:
            events.append(dict(event=index,covered=False));continue
        first,last=event['first_frame'],event['last_frame']
        high=quality['events'][index-1]
        if (high['first_frame'],high['last_frame'])!=(first,last):raise ValueError('Quality selection changed')
        item=dict(event=index,covered=True,first_frame=first,last_frame=last,metrics={},nes_very_high=high['nes']['Very High'])
        card=f'<section><h2>Event {index}: source frames {first}–{last}</h2><p>Fixed selection; independent source-frame audio bounds, no local alignment.</p>'
        for key in ('parent_normal','normal','parent_noise','noise'):
            r=rows[key];pcm=arrays[key]
            a,b=r[first-1]['start_sample'],r[last-1]['end_sample']
            item['metrics'][key]=measure(pcm,32040,a,b)
            c=r[max(0,first-16)]['start_sample'];d=r[min(len(r),last+15)-1]['end_sample']
            name=f'event-{index:02}-{key}.wav';wavfile.write(out/name,32040,pcm[c:d])
            clips.append(dict(file=name,source=str(paths[key]/'audio.wav'),first=c,last=d,rate=32040))
            card+=f'<h3>{key}</h3><audio controls src="{name}"></audio>'+waveform_svg(pcm[a:b])
        card+='<pre>'+html.escape(json.dumps(item,indent=2))+'</pre></section>'
        cards.append(card);events.append(item)
    closer=sum(abs(e['metrics']['noise']['spectral_centroid_hz']-e['nes_very_high']['spectral_centroid_hz']) <
        abs(e['metrics']['parent_noise']['spectral_centroid_hz']-e['nes_very_high']['spectral_centroid_hz']) for e in events if e['covered'])
    peak_ratios=[e['metrics']['noise']['peak']/e['metrics']['parent_noise']['peak'] for e in events if e['covered']]
    mix_step_increases=[e['event'] for e in events if e['covered'] and e['metrics']['normal']['max_step']>e['metrics']['parent_normal']['max_step']]
    result=dict(noise_prototype=detail,proofs=proofs,noise_states=noise_states,
        nonnoise_ready_differences=nonnoise,timeline_field_differences=timeline_diffs,
        first_packet_host_frames=[rows[k][0]['host_frame'] for k in ('parent_normal','normal')],
        stem_composition=mix,events=events,clips=clips,centroid_closer_to_very_high_windows=closer,
        noise_peak_ratio_range=[min(peak_ratios),max(peak_ratios)],mix_step_increased_events=mix_step_increases,
        covered_windows=sum(e['covered'] for e in events),release_ready=False,deployed=False,
        scope='Offline binary BRR source trial. Spectral distance is descriptive, not an acceptance gate. '
        'One held loop sample; rates0/1 and short mode unsupported. Pitch quantum/interpolation, loop seam, '
        'other-voice timing, actual noise pitch latching and full-game budgets remain unqualified.',sources=sources)
    page='<!doctype html><meta charset="utf-8"><title>Binary BRR noise prototype</title><style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1000px;margin:30px auto}a{color:#8df}svg{width:100%}pre{white-space:pre-wrap}section{border-top:1px solid #789}</style>'
    page+='<h1>Binary BRR noise: offline prototype, not deployed</h1><p>'+html.escape(result['scope'])+'</p>'
    page+=f'<p>Centroid closer to Very High NES in {closer}/{result["covered_windows"]} fixed windows. Not a subjective or pop-free verdict.</p>'
    page+=f'<p><strong>Retained regression:</strong> noise peaks are only {min(peak_ratios):.1%}–{max(peak_ratios):.1%} of the parent. Lower steps cannot be credited as fidelity when the sound level changed. Full-mix step increases at events {mix_step_increases} remain. First packet starts {result["first_packet_host_frames"][1]-result["first_packet_host_frames"][0]} frames later because this fixture uploads a larger engine/sample image.</p>'
    page+='<p>Matching non-noise DSP registers at packet completion does not prove unchanged music waveforms or oscillator phase.</p>'
    page+='<p><a href="../'+paths['quality'].name+'/">All three NES quality references</a> · <a href="report.json">Every observation and source hash</a></p>'
    page+='<pre>'+html.escape(json.dumps({k:result[k] for k in ('proofs','timeline_field_differences','first_packet_host_frames','nonnoise_ready_differences')},indent=2))+'</pre>'+''.join(cards)
    (out/'index.html').write_text(page);result['artifacts']={p.name:sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(closer_windows=closer,nonnoise_ready_differences=len(nonnoise),proofs=proofs,timeline=timeline_diffs)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
