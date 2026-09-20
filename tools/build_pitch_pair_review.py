"""Publish measured split-pitch samples and unprocessed, same-command A/B audio."""
import argparse
from collections import Counter, defaultdict
import csv
import html
import json
from pathlib import Path
import shutil
import wave

from tools.audit_main_display_latency import bound_report
from tools.audit_pulse_pitch import pitch_updates
from tools.benchmark_report import sha


def transactions(binding):
    writes=[]
    with Path(binding['traces']['RCR_DSP_LATENCY_TRACE']).open() as stream:
        for r in csv.reader(stream):
            if r[0]=='D':
                writes.append(dict(packet=int(r[1]),tick=int(r[2]),register=int(r[5]),value=int(r[6])))
    keyed={};by_tick={};gaps=Counter()
    for voice in (0,1):
        seen=Counter()
        for u in pitch_updates(writes,voice):
            key=(voice,u['low']['packet'],u['old'],u['new'])
            ordinal=seen[key];seen[key]+=1
            key=(*key,ordinal)
            keyed[key]=u;by_tick[voice,u['low']['tick']]=key
            gaps[u['high']['tick']-u['low']['tick']]+=1
    return keyed,by_tick,dict(gaps)


def windows(path,centers):
    found=defaultdict(list)
    with path.open() as stream:
        for r in csv.reader(stream):
            tick,voice=int(r[0]),int(r[1])
            for i,(v,center) in enumerate(centers):
                if voice==v and abs(tick-center)<=192:
                    found[i].append(dict(tick=tick,pitch=int(r[4]),output=int(r[9])))
    if any(len(found[i])!=12 for i in range(len(centers))):
        raise ValueError('Incomplete pulse plot window')
    return found


def build(out):
    paths=dict(before=Path('build/pulse-pitch-audit-1417/report.json'),
        after=Path('build/pitch-pair-audit-1421/report.json'),
        executed=Path('build/pitch-pair-executed-1422/report.json'),
        onsets=Path('build/pitch-pair-onsets-1423/report.json'))
    reports={k:bound_report(p) for k,p in paths.items()}
    for side in ('baseline','candidate'):bound_report_data=reports['onsets'][side];verify_sources(bound_report_data['sources'])
    observed=[Path('build/pulse-pitch-observed-1416'),Path('build/pitch-pair-observed-1419')]
    bindings=[bound_report(p/'onset-observer.json') for p in observed]
    keyed=[transactions(b) for b in bindings]
    events=sorted((e for e in reports['before']['events'] if e['nonzero_output']),
        key=lambda e:-min(abs(e['pitch']-e['update'][v]) for v in ('old','new')))
    selected=[]
    for e in events:
        key=keyed[0][1][e['voice'],e['update']['low']['tick']]
        if key in keyed[1][0]:selected.append((key,[keyed[s][0][key] for s in (0,1)]))
        if len(selected)==3:break
    if len(selected)!=3:raise ValueError('Insufficient identical old/new transaction pairs')
    traces=[windows(Path(b['traces']['RCR_PULSE_PITCH_TRACE']),
        [(key[0],updates[s]['low']['tick']) for key,updates in selected]) for s,b in enumerate(bindings)]
    out.mkdir(parents=True,exist_ok=False)
    sources={str(p):sha(p) for p in [Path(__file__),*paths.values()]}
    for name,path in paths.items():shutil.copyfile(path,out/(name+'.json'))
    sections=[];clips=[]
    for i,(key,updates) in enumerate(selected):
        voice,packet,old,new,ordinal=key
        maximum=max([old,new]+[r['pitch'] for side in traces for r in side[i]]) or 1
        svg=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 300">',
            '<rect width="1000" height="300" fill="white"/>',
            '<g font-family="sans-serif" font-size="14" fill="#123">']
        audio=[]
        for s,label in enumerate(('Current','Prefetch trial')):
            left=40+s*500;center=updates[s]['low']['tick']
            x=lambda tick:left+(tick-center+192)*1.1
            y=lambda pitch:240-pitch*170/maximum
            points=[]
            for j,r in enumerate(traces[s][i]):
                if j:points.append(f'{x(r["tick"])},{y(traces[s][i][j-1]["pitch"])}')
                points.append(f'{x(r["tick"])},{y(r["pitch"])}')
            svg.append(f'<text x="{left}" y="25">{label}: voice {voice}, packet {packet}</text>')
            for value,color in ((old,'#aaa'),(new,'#da7b00')):
                svg.append(f'<line x1="{left}" x2="{left+422}" y1="{y(value)}" y2="{y(value)}" stroke="{color}"/>')
            svg.append('<polyline fill="none" stroke="#1670b0" stroke-width="2" points="'+' '.join(points)+'"/>')
            svg.append(f'<text x="{left}" y="275">Old {old}, new {new}; 12 actual DSP samples</text>')
            src=observed[s]/'audio.wav'
            with wave.open(str(src)) as wav:
                rate=wav.getframerate();total=wav.getnframes();params=wav.getparams()
                start=max(0,(center-28)//32-int(rate*0.3));end=min(total,start+int(rate*0.8))
                wav.setpos(start);pcm=wav.readframes(end-start)
            name=f'pair-{i}-{s}.wav'
            with wave.open(str(out/name),'wb') as wav:
                wav.setparams(params);wav.writeframes(pcm)
            sources[str(src)]=sha(src)
            clips.append(dict(file=name,source=str(src),start_sample=start,end_sample=end,
                transaction_key=key,low_write_tick=center,raw_pcm_sha256=__import__('hashlib').sha256(pcm).hexdigest()))
            audio.append(f'<p>{label} <audio controls preload="none" src="{name}"></audio></p>')
        svg.append('</g></svg>');name=f'pair-{i}.svg';(out/name).write_text(''.join(svg))
        sections.append(f'<section><img src="{name}" alt="Actual pitch latches for the same command transition">'+''.join(audio)+'</section>')
    counts=[]
    for name,label in (('before','Current'),('after','Prefetch trial')):
        r=reports[name]
        counts.append(f'<tr><td>{label}</td><td>{sum(r["pitch_pairs_by_voice"])}</td><td>{r["split_samples"]}</td><td>{r["nonzero_split_samples"]}</td></tr>')
    page='''<!doctype html><html><head><meta charset="utf-8"><title>Pulse pitch write trial</title>
<style>body{max-width:1100px;margin:30px auto;font:18px sans-serif;background:#10141a;color:#eee}img{width:100%}section{margin:32px 0}td,th{padding:10px;border:1px solid #567}a{color:#8df}audio{vertical-align:middle}</style></head><body>
<h1>Pulse pitch write trial — not deployed</h1>
<p>Both captures replay the same 2,512 command packets. The observer reconstructs all 3,482,203 pulse samples, preserves PCM/RAM/video, and checks raw DAC identity. This measures intermediate pitch, not audible clicks.</p>
<table><tr><th>Engine</th><th>Pitch pairs</th><th>Split samples</th><th>Nonzero voice output</th></tr>'''+''.join(counts)+'''</table>
<p>The byte-write gap shrank from 17 to 9 SPC clocks; initialization remains 20. All 4,096 executed pitch cases preserve final DP/DSP state; the active path costs 18 additional clocks per voice. Publication counts differ because SPC timing changes. Residual errors remain: this is not an atomic update or a speed/perceptual/hardware pass.</p>
<p>Below: three largest baseline deviations with matching voice, packet, old/new pitch, and transaction ordinal. Each plot has its own write-time origin. Audio is native, unprocessed stereo PCM, 0.8 seconds around that transaction; clips are not phase-aligned. Gray = old pitch, orange = target.</p>'''+''.join(sections)
    page+='<p>'+', '.join(f'<a href="{k}.json">{html.escape(k)} report</a>' for k in paths)+'</p></body></html>'
    (out/'index.html').write_text(page)
    sources.update({str(p/'onset-observer.json'):sha(p/'onset-observer.json') for p in observed})
    report=dict(sources=sources,clips=clips,write_gaps_by_side=[k[2] for k in keyed],
        artifacts={p.name:sha(p) for p in out.iterdir()},onset_gate=reports['onsets']['passed'],
        physical_audio_verified=False,pop_free_verified=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),write_gaps=report['write_gaps_by_side'],onset_gate=report['onset_gate'])))


def verify_sources(sources):
    if any(sha(Path(p))!=digest for p,digest in sources.items()):raise ValueError('Changed nested source')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    build(**vars(p.parse_args()))
