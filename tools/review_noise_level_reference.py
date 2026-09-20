"""Measure held noise timbre and noise/pulse level ratios without audio fitting."""
import argparse
import csv
import html
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from tools.audit_main_display_latency import bound_report
from tools.audit_recorded_transients import waveform_svg
from tools.benchmark_report import sha
from tools.build_noise_level_reference import stimulus
from tools.review_native_transient_stems import read,same_core_load
from tools.review_noise_packet_reference import validate_timeline
from tools.review_noise_quality_reference import reconstruct_quality


def measure(pcm,rate,first,last):
    if pcm.dtype!=np.int16 or pcm.ndim!=2 or pcm.shape[1]!=2 or not 0<first<last<=len(pcm):
        raise ValueError('Need native stereo PCM and a complete window')
    x=pcm[first:last].astype(float);ac=x-x.mean(axis=0)
    rms=np.sqrt(np.mean(ac**2,axis=0))
    if not np.all(rms>0):raise ValueError('Dead held-tone channel')
    power=np.abs(np.fft.rfft(ac[:,0]*np.hanning(len(ac))))**2
    hz=np.fft.rfftfreq(len(ac),1/rate);energy=power.sum()
    cumulative=np.cumsum(power)/energy
    return dict(first_sample=first,last_sample=last,rate=rate,ac_rms=rms.tolist(),
        dc_mean=x.mean(axis=0).tolist(),peak=int(np.abs(x).max()),
        max_step=int(np.abs(x-pcm[first-1:last-1].astype(float)).max()),
        centroid_hz=float(np.dot(power,hz)/energy),
        median_power_hz=float(hz[np.searchsorted(cumulative,.5)]),
        power95_hz=float(hz[np.searchsorted(cumulative,.95)]),
        clipped_samples=int(np.count_nonzero(np.abs(x)>=32767)))


def build(manifest,out):
    if out.exists():raise ValueError('Fresh review required')
    paths={k:Path(v) for k,v in json.loads(manifest.read_text()).items()}
    sources={str(p):sha(p) for p in (manifest,Path(__file__),Path('tools/build_noise_level_reference.py'),
        Path('tools/audit_main_display_latency.py'),Path('tools/review_noise_quality_reference.py'),
        Path('tools/audit_nes_filter.py'),Path('tools/review_native_transient_stems.py'),
        Path('tools/review_noise_packet_reference.py'),Path('tools/audit_recorded_transients.py'))}
    def report(p):
        r=bound_report(p);sources[str(p)]=sha(p);sources.update(r['sources']);return r
    grouped,packets,cases=stimulus()
    fixtures={s:paths.get(s+'_fixture',paths['fixture']/s) for s in ('nes','parent','trial')}
    specs={s:report(fixtures[s]/'manifest.json') for s in fixtures}
    if any(s['cases']!=cases or s['source_frames']!=len(grouped) for s in specs.values()):raise ValueError('Different test cases')
    nes=report(paths['nes']/'report.json');observed=report(paths['nes_observed']/'report.json')
    cores=[{k:v for k,v in r['sources'].items() if k.endswith('.so')} for r in (nes,observed)]
    if len(cores[0])!=1 or cores[0]!=cores[1]:raise ValueError('Need same-core NES observer/control')
    for name in ('audio.wav','timeline.json','memory.ram'):
        if sha(paths['nes']/name)!=sha(paths['nes_observed']/name):raise ValueError('NES observer changed execution')
    arrays={s:read(paths[s]/'audio.wav',48000 if s=='nes' else 32040) for s in ('nes','parent','trial')}
    rows={s:json.loads((paths[s]/'timeline.json').read_text()) for s in arrays}
    for s in arrays:
        validate_timeline(rows[s],len(grouped),len(arrays[s]))
        for n in ('audio.wav','timeline.json'):
            p=paths[s]/n;sources[str(p)]=sha(p)
    raw_path=Path(observed['traces']['samples']);block_path=Path(observed['traces']['blocks'])
    raw=np.fromfile(raw_path,dtype='<i4').reshape(-1,2)
    with block_path.open() as file:blocks=list(csv.reader(file))
    checked=reconstruct_quality(raw,blocks,arrays['nes'],48000,2)
    sources[str(raw_path)]=sha(raw_path);sources[str(block_path)]=sha(block_path)
    proofs={};spc_cores=[]
    for s in ('parent','trial'):
        normal=report(paths[s]/'report.json')
        spc_cores.append({k:v for k,v in normal['sources'].items() if k.endswith('.so')})
        r,_,_,ready=same_core_load(paths[s+'_observed'],paths[s],fixtures[s])
        sources.update(r['sources'])
        proofs[s]={k:r[k] for k in ('observer_neutral','raw_dac_identical','received_packets','eligible','wrong_first_pitch','stale_nonzero_onsets')}
        if r['wrong_first_pitch'] or r['stale_nonzero_onsets']:raise ValueError('Pulse onset regression')
        if [row['packet'] for row in rows[s]]!=[p.hex() for p in packets]:raise ValueError('Different received schedule')
        # Every noise completion must select the expected source and control.
        for c in cases:
            if c['channel']!='noise':continue
            for number in range(c['first_frame'],c['last_frame']+1):
                regs=ready[number]['registers']
                if regs[0x30]!=2*c['volume'] or regs[0x31]!=2*c['volume'] or regs[0x37]!=31:
                    raise ValueError('Noise volume/GAIN did not follow held command')
                fallback=specs[s].get('noise_prototype',{}).get('fallback_rates',[])
                expected_non=8 if s=='parent' or c['period'] in fallback else 0
                if regs[0x3d]!=expected_non:raise ValueError('Wrong noise source')
                if s=='trial' and regs[0x34]!=5:raise ValueError('Wrong BRR sample')
                if s=='trial' and not expected_non and 'noise_prototype' in specs[s]:
                    if regs[0x32]+256*regs[0x33]!=specs[s]['noise_prototype']['pitches'][c['period']]:
                        raise ValueError('Wrong doubled noise pitch')
    if spc_cores[0]!=spc_cores[1]:raise ValueError('Cross-engine core mismatch')
    out.mkdir(parents=True);measurements=[];clips=[];cards=[]
    for index,c in enumerate(cases,1):
        first,last=c['first_frame']+16,c['last_frame']-16
        item=dict(**c,measured_first_frame=first,measured_last_frame=last,systems={})
        card=f'<section><h2>{index}: {c["channel"]}, period {c["period"]}, volume {c["volume"]}</h2>'
        for s in ('nes','parent','trial'):
            rate=48000 if s=='nes' else 32040;r=rows[s];pcm=arrays[s]
            a,b=r[first-1]['start_sample'],r[last-1]['end_sample']
            item['systems'][s]=measure(pcm,rate,a,b)
            start,end=r[c['first_frame']-1]['start_sample'],r[c['last_frame']-1]['end_sample']
            name=f'case-{index:02}-{s}.wav';wavfile.write(out/name,rate,pcm[start:end])
            clips.append(dict(file=name,source=str(paths[s]/'audio.wav'),first=start,last=end,rate=rate))
            card+=f'<h3>{s}</h3><audio controls src="{name}"></audio>'+waveform_svg(pcm[a:b])
        measurements.append(item);cards.append(card+'</section>')
    pulse={c['volume']:c['systems'] for c in measurements if c['channel']=='pulse'}
    for c in measurements:
        if c['channel']=='noise':
            c['noise_to_pulse_ac_ratio']={s:c['systems'][s]['ac_rms'][0]/pulse[c['volume']][s]['ac_rms'][0] for s in arrays}
    tail={s:dict(first_sample=rows[s][-16]['start_sample'],last_sample=rows[s][-1]['end_sample'],
        peak=int(np.abs(arrays[s][rows[s][-16]['start_sample']:rows[s][-1]['end_sample']].astype(np.int32)).max())) for s in arrays}
    closer=sum(abs(c['systems']['trial']['centroid_hz']-c['systems']['nes']['centroid_hz']) < abs(c['systems']['parent']['centroid_hz']-c['systems']['nes']['centroid_hz']) for c in measurements if c['channel']=='noise')
    fallback=specs['trial'].get('noise_prototype',{}).get('fallback_rates',[])
    changed=[c for c in measurements if c['channel']=='noise' and c['period'] not in fallback]
    changed_closer=sum(abs(c['systems']['trial']['centroid_hz']-c['systems']['nes']['centroid_hz']) < abs(c['systems']['parent']['centroid_hz']-c['systems']['nes']['centroid_hz']) for c in changed)
    result=dict(measurements=measurements,tail=tail,proofs=proofs,nes_filter_samples_reconstructed=checked,
        trial_prototype=specs['trial'].get('noise_prototype',{'variant':'one-sample-per-bit original prototype'}),
        cases=len(cases),source_frames=len(grouped),noise_centroid_closer_cases=closer,
        changed_source_cases=len(changed),changed_source_closer_cases=changed_closer,
        fallback_noise_cases=28-len(changed),
        clips=clips,sources=sources,release_ready=False,scope='Fixed middle32 frames of each held64-frame case. Native PCM unchanged. Ratios are analysis, not applied gains. No waveform phase/time fitting, automatic fidelity threshold or physical pop verdict.')
    page='<!doctype html><meta charset="utf-8"><title>Isolated noise rates and channel levels</title><style>body{background:#101820;color:#eef;font:16px system-ui;max-width:1150px;margin:25px auto}a{color:#8df}td,th{padding:7px;text-align:right}svg{width:100%}section{border-top:1px solid #789}pre{white-space:pre-wrap}</style>'
    page+='<h1>Held noise: rate, spectrum and relative channel level</h1><p>'+html.escape(result['scope'])+'</p>'
    page+=f'<p>BRR-source centroid closer in {changed_closer}/{len(changed)} changed-source cases. All-case raw tally: {closer}/28. The {28-len(changed)} unchanged-source fallback cases are not credited as synthesis improvements. Descriptive only; short mode, fast-rate fidelity, transitions and loop/pitch issues remain. No deployment.</p>'
    page+='<details><summary>Exact prototype layout and limitations</summary><pre>'+html.escape(json.dumps(result['trial_prototype'],indent=2))+'</pre></details>'
    page+='<table><tr><th>Period</th><th>Vol</th><th>NES Hz</th><th>Parent Hz</th><th>Trial Hz</th><th>NES noise/pulse</th><th>Parent</th><th>Trial</th></tr>'
    for c in measurements:
        if c['channel']!='noise':continue
        page+=f'<tr><td>{c["period"]}</td><td>{c["volume"]}</td>'+''.join(f'<td>{c["systems"][s]["centroid_hz"]:.1f}</td>' for s in arrays)+''.join(f'<td>{c["noise_to_pulse_ac_ratio"][s]:.3f}</td>' for s in arrays)+'</tr>'
    page+='</table><p><a href="report.json">All measurements and evidence bindings</a></p><details><summary>Execution checks and final mute</summary><pre>'+html.escape(json.dumps(dict(proofs=proofs,tail=tail),indent=2))+'</pre></details>'+''.join(cards)
    (out/'index.html').write_text(page);result['artifacts']={p.name:sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(cases=len(cases),closer=closer,proofs=proofs,tail=tail,nes_filter_samples=checked)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
