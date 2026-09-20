"""Keep frozen noise-event selections while comparing all three NES quality paths."""
import argparse
import csv
import html
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from tools.audit_main_display_latency import bound_report
from tools.audit_nes_filter import step
from tools.benchmark_report import sha
from tools.capture_noise_quality_reference import QUALITIES
from tools.review_noise_packet_reference import measure, validate_timeline


def reconstruct_quality(raw,blocks,pcm,rate,quality):
    if quality not in (0,1,2):raise ValueError('Unsupported quality')
    if (raw.dtype!=np.dtype('<i4') or raw.ndim!=2 or raw.shape[1]!=2 or
            pcm.dtype!=np.int16 or pcm.shape!=raw.shape or
            not np.array_equal(raw[:,1],pcm[:,0]) or not np.array_equal(raw[:,1],pcm[:,1])):
        raise ValueError('Observed filter output differs from native PCM')
    end=acc1=acc2=0
    # Default core sound volume is150; its existing quality paths use different
    # accumulator scales, not a fitted gain. This checker deliberately pins it.
    expected_volume=147456 if quality==0 else 18432
    for block in blocks:
        if len(block)!=10:raise ValueError('Malformed filter block')
        start,count,hz,q,rf,mul1,mul2,volume,a1,a2=map(int,block)
        if (start!=end or count<=0 or start+count>len(raw) or hz!=rate or q!=quality or rf!=0 or
                mul1!=(94<<16)//rate or mul2!=(24<<16)//rate or volume!=expected_volume or
                (a1,a2)!=(acc1,acc2)):
            raise ValueError('Actual quality/filter state differs')
        for value,observed in raw[start:start+count].tolist():
            predicted,acc1,acc2=step(value,acc1,acc2,mul1,mul2,volume)
            if predicted!=observed:raise ValueError('Filter recurrence mismatch')
        end=start+count
    if end!=len(raw):raise ValueError('Incomplete filter trace')
    return end


def build(manifest,out):
    if out.exists():raise ValueError('Fresh review required')
    spec=json.loads(manifest.read_text());selection=Path(spec['selection'])
    prior=bound_report(selection/'report.json')
    if set(spec['runs'])!=set(QUALITIES):raise ValueError('Need all three reference quality paths')
    sources={str(p):sha(p) for p in (Path(__file__),manifest,selection/'report.json',
        Path('tools/audit_nes_filter.py'),Path('tools/review_noise_packet_reference.py'),
        Path('tools/audit_main_display_latency.py'))}
    sources.update(prior['sources'])
    runs={};cores=[];roms=[];stimuli=[];logical=[]
    for quality in QUALITIES:
        paths={k:Path(v) for k,v in spec['runs'][quality].items()}
        a,b=(bound_report(paths[k]/'report.json') for k in ('normal','observed'))
        if any(r['quality']!=quality or not r['passed'] or
               r['options_queried']!={'fceumm_sndquality':quality,'fceumm_sndlowpass':'disabled'} or
               not r['post_load_update_delivered'] for r in (a,b)):
            raise ValueError('Wrong requested quality or unapplied options')
        core=[{k:v for k,v in r['sources'].items() if k.endswith('.so')} for r in (a,b)]
        if len(core[0])!=1 or core[0]!=core[1]:raise ValueError('Need same-core normal/observer')
        cores.append(core[0])
        for name in ('audio.wav','timeline.json','memory.ram','player.nes','stimulus.bin'):
            if sha(paths['normal']/name)!=sha(paths['observed']/name):
                raise ValueError('Observer changed replay')
        for p,r in ((paths['normal'],a),(paths['observed'],b)):
            sources[str(p/'report.json')]=sha(p/'report.json');sources.update(r['sources'])
        roms.append(sha(paths['normal']/'player.nes'));stimuli.append(sha(paths['normal']/'stimulus.bin'))
        rate,pcm=wavfile.read(paths['normal']/'audio.wav')
        if rate!=48000:raise ValueError('Unexpected native NES rate')
        rows=json.loads((paths['normal']/'timeline.json').read_text())
        validate_timeline(rows,a['source_frames'],len(pcm))
        logical.append([{k:v for k,v in r.items() if k not in ('start_sample','end_sample')} for r in rows])
        trace=Path(b['traces']['samples']);blocks_path=Path(b['traces']['blocks'])
        raw=np.fromfile(trace,dtype='<i4').reshape(-1,2)
        with blocks_path.open() as file:blocks=list(csv.reader(file))
        q=QUALITIES.index(quality);checked=reconstruct_quality(raw,blocks,pcm,rate,q)
        # Execute corruption controls against the real observed data.
        corrupt=[list(row) for row in blocks];corrupt[0][3]=str((q+1)%3)
        controls={}
        for label,r,bb in (('wrong_quality',raw,corrupt),('wrong_input',raw.copy(),blocks)):
            if label=='wrong_input':r[len(r)//2,0]+=32768
            try:reconstruct_quality(r,bb,pcm,rate,q)
            except ValueError as error:controls[label]=str(error)
            else:raise ValueError('Corrupt observer control escaped detection')
        sources[str(trace)]=sha(trace);sources[str(blocks_path)]=sha(blocks_path)
        runs[quality]=dict(pcm=pcm,rows=rows,rate=rate,checked_samples=checked,
            checked_blocks=len(blocks),controls=controls,source=str(paths['normal']/'audio.wav'))
    if any(c!=cores[0] for c in cores) or len(set(roms))!=1 or len(set(stimuli))!=1:
        raise ValueError('Cross-quality core or stimulus differs')
    if any(x!=logical[0] for x in logical):raise ValueError('Quality changed CPU/write execution')
    # Explicit Low must reproduce the original selection reference exactly.
    reference=Path(spec['reference'])
    for name in ('audio.wav','timeline.json','player.nes','stimulus.bin'):
        if sha(Path(spec['runs']['Low']['normal'])/name)!=sha(reference/name):
            raise ValueError('Explicit Low does not reproduce the original reference')
        sources[str(reference/name)]=sha(reference/name)
    if prior['sources'].get(str(reference/'audio.wav'))!=sha(reference/'audio.wav'):
        raise ValueError('Selection from a different reference')
    out.mkdir(parents=True);events=[];clips=[];cards=[]
    for index,event in enumerate(prior['events'],1):
        if not event['mapped']['covered']:
            events.append(dict(event=index,covered=False,reason=event['mapped']['reason']));continue
        first,last=event['first_frame'],event['last_frame']
        result=dict(event=index,covered=True,first_frame=first,last_frame=last,
            snes=event['metrics']['snes'],nes={})
        card=f'<section><h2>Event {index}: source frames {first}–{last}</h2>'
        card+='<p>SNES centroid: '+f'{result["snes"]["spectral_centroid_hz"]:.2f} Hz. No waveform alignment.</p>'
        for quality,data in runs.items():
            rows=data['rows'];pcm=data['pcm'];rate=data['rate']
            a,b=rows[first-1]['start_sample'],rows[last-1]['end_sample']
            result['nes'][quality]=measure(pcm,rate,a,b)
            c=rows[max(0,first-16)]['start_sample'];d=rows[min(len(rows),last+15)-1]['end_sample']
            name=f'event-{index:02}-{quality.lower().replace(" ","-")}.wav'
            wavfile.write(out/name,rate,pcm[c:d])
            clips.append(dict(file=name,source=data['source'],first=c,last=d,rate=rate))
            card+=f'<h3>{quality}</h3><audio controls src="{name}"></audio>'
        card+='<pre>'+html.escape(json.dumps(result['nes'],indent=2))+'</pre></section>'
        cards.append(card);events.append(result)
    summary={q:dict(checked_samples=d['checked_samples'],checked_blocks=d['checked_blocks'],
        controls=d['controls'],total_samples=len(d['pcm']),first_source_sample=d['rows'][0]['start_sample'],
        snes_centroid_higher_windows=sum(e['snes']['spectral_centroid_hz']>e['nes'][q]['spectral_centroid_hz'] for e in events if e['covered']))
        for q,d in runs.items()}
    report=dict(quality_runs=summary,events=events,clips=clips,sources=sources,release_ready=False,
        physical_causality_proven=False,scope='Same source-frame windows and byte-identical NES stimulus across actual quality0/1/2 paths; native callback/sample boundaries remain independent. Existing physical selection, not phase-fitted audio. Emulator quality labels do not establish NES hardware fidelity.')
    page='<!doctype html><meta charset="utf-8"><title>NES noise quality control</title><style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1050px;margin:30px auto}a{color:#8df}pre{white-space:pre-wrap}section{border-top:1px solid #789}</style>'
    page+='<h1>Noise reference: Low / High / Very High</h1><p>'+html.escape(report['scope'])+'</p>'
    page+='<p>RF filter disabled throughout; actual quality observed in every output block. All integer filter samples reconstructed. Every listening clip is an untouched native slice. No SNES cartridge changes.</p>'
    page+='<p><a href="../'+selection.name+'/">Original selection, SNES clips and waveforms</a> · <a href="report.json">All evidence</a></p>'
    page+='<pre>'+html.escape(json.dumps(summary,indent=2))+'</pre>'+''.join(cards)
    (out/'index.html').write_text(page);report['artifacts']={p.name:sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(summary))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','out'):parser.add_argument('--'+name,type=Path,required=True)
    build(**vars(parser.parse_args()))
