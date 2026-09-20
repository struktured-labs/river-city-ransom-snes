"""Current-cartridge native audio edges, exact mixer contributions and measured packet cadence."""
import argparse
from bisect import bisect_right
import html
import json
from pathlib import Path
import wave

import numpy as np

from tools.audit_dsp_latency import next_dac_sample
from tools.audit_noise_game import same_execution
from tools.audit_postpublish_keyon import load
from tools.audit_gameplay_transients import _svg
from tools.benchmark_report import sha,verify_capture
from tools.capture_audio_stem import options_for
from tools.frame_audit import verify_frame
from tools.review_native_transient_stems import composition


def read(path):
    with wave.open(str(path)) as f:
        if f.getnchannels()!=2 or f.getsampwidth()!=2:raise ValueError('Need native stereo PCM16')
        return f.getframerate(),np.frombuffer(f.readframes(f.getnframes()),'<i2').reshape(-1,2)


def select_edges(pcm,rate,eligible,count=12):
    if len(eligible)!=len(pcm) or pcm.ndim!=2 or pcm.shape[1]!=2 or rate<=0:
        raise ValueError('Invalid sample selection')
    steps=np.abs(np.diff(pcm.astype(np.int32),axis=0));remaining=steps.max(axis=1)
    remaining[~(eligible[1:]&eligible[:-1])]=-1
    events=[]
    for _ in range(count):
        at=int(remaining.argmax())
        if remaining[at]<0:break
        channel=int(steps[at].argmax());sample=at+1
        events.append(dict(sample=sample,channel=channel,step=int(steps[at,channel])))
        remaining[max(0,at-rate//2):min(len(remaining),at+rate//2+1)]=-1
    return events


def contribution(pcm,event):
    at,ch=event['sample'],event['channel']
    return dict(before=int(pcm[at-1,ch]),after=int(pcm[at,ch]),step=int(pcm[at,ch])-int(pcm[at-1,ch]))


def review(candidate,capture,normal,noise,rest,out):
    if out.exists():raise ValueError('Fresh audio review required')
    audit,writes,ready=load(capture,normal,candidate);receipt,rows=verify_capture(capture)
    rate,full=read(capture/'audio.wav');arrays={'full':full};sources=dict(audit['sources'])
    for label,root,mode in (('noise',noise,'noise'),('rest',rest,'without-noise')):
        r,timeline=verify_capture(root);same_execution(rows,timeline)
        if r['core_sha256']!=receipt['core_sha256'] or r['rom_sha256']!=receipt['rom_sha256']:
            raise ValueError('Different core or cartridge for stem')
        stem=r['audio_stem'];wanted={k.decode():v.decode() for k,v in options_for('snes',mode).items()}
        if not stem['post_load_update_delivered'] or stem['options_queried']!=wanted:
            raise ValueError('Stem options not delivered')
        sr,pcm=read(root/'audio.wav')
        if sr!=rate:raise ValueError('Changed native sample rate')
        arrays[label]=pcm
        for p in root.iterdir():
            if p.is_file():sources[str(p)]=sha(p)
    mix=composition(full,arrays['noise'],arrays['rest'])
    starts=[r['audio_start_sample'] for r in rows];eligible=np.zeros(len(full),dtype=bool)
    for row in rows:
        ram=bytes.fromhex(row['game_ram_hex'])
        if ram[0x100]&0xc0==0xc0:
            a=row['audio_start_sample'];eligible[a:a+row['audio']['samples']]=True
    selected=select_edges(full,rate,eligible)
    if len(selected)!=12:raise ValueError('Incomplete gameplay event coverage')
    intervals=[];items=sorted(ready.items())
    for (a,ta),(b,tb) in zip(items,items[1:]):
        if b!=a+1 or tb<=ta:raise ValueError('Nonmonotonic completed packets')
        lo=bisect_right(starts,next_dac_sample(ta))-1;hi=bisect_right(starts,next_dac_sample(tb))-1
        if not 0<=lo<=hi<len(rows):raise ValueError('Packet outside PCM coverage')
        context=rows[lo:hi+1]
        stable=all((bytes.fromhex(r['game_ram_hex'])[0x100]&0xc0)==0xc0 and
                   not r['native']['transition_state'] for r in context)
        if stable:
            intervals.append(dict(first_packet=a,last_packet=b,first_frame=lo+1,last_frame=hi+1,
                phase=rows[hi]['phase'],spc_clocks=tb-ta,dac_samples=(tb-ta)/32,
                seconds=(tb-ta)/(32*rate)))
    if not intervals:raise ValueError('No gameplay cadence coverage')
    deltas=np.array([v['dac_samples'] for v in intervals])
    cadence=dict(intervals=len(intervals),minimum_samples=float(deltas.min()),
        median_samples=float(np.median(deltas)),p99_samples=float(np.quantile(deltas,.99)),
        maximum_samples=float(deltas.max()),longest=sorted(intervals,key=lambda v:v['spc_clocks'],reverse=True)[:12],
        scope='Actual consecutive SPC completion ticks during gameplay without transition-state flags. '
        'Pause and original-busy states are not filtered. Variable intervals are measurements, not diagnosed sound defects.')
    out.mkdir(parents=True);cards=[];events=[];clips=[];write_samples=[next_dac_sample(w['tick']) for w in writes]
    roots=dict(full=capture,noise=noise,rest=rest)
    for i,e in enumerate(selected,1):
        row=rows[bisect_right(starts,e['sample'])-1]
        pieces={label:contribution(pcm,e) for label,pcm in arrays.items()}
        first=max(0,e['sample']-rate//2);last=min(len(full),e['sample']+rate//2)
        event=dict(e,frame=row['frame'],phase=row['phase'],seconds=e['sample']/rate,contributions=pieces,
            nearby_dsp_writes=writes[max(0,bisect_right(write_samples,e['sample'])-6):bisect_right(write_samples,e['sample'])+6])
        events.append(event);players=[]
        for label,pcm in arrays.items():
            name=f'event-{i:02}-{label}.wav'
            with wave.open(str(out/name),'wb') as f:
                f.setnchannels(2);f.setsampwidth(2);f.setframerate(rate);f.writeframes(pcm[first:last].tobytes())
            sr,cut=read(out/name)
            if sr!=rate or not np.array_equal(cut,pcm[first:last]):raise ValueError('Changed audition samples')
            clips.append(dict(file=name,source=str(roots[label]/'audio.wav'),first=first,last=last))
            players.append(f'<p>{label}</p><audio controls preload="none" src="{name}"></audio>')
        source=verify_frame(capture,row);target=f'event-{i:02}.png'
        import shutil
        shutil.copy2(source,out/target);sources[str(source)]=sha(source)
        cards.append(f'<section><h2>#{i} · frame {row["frame"]} · {html.escape(row["phase"])}</h2>'
            f'<img src="{target}"><pre>'+html.escape(json.dumps(pieces,indent=2))+'</pre>'+''.join(players)+
            _svg(full,e['sample'],32768)+'</section>')
    # Negative controls independently damage a stem and remove eligible input.
    bad=arrays['noise'].copy();bad[selected[0]['sample'],selected[0]['channel']]^=1024
    rejected=False
    try:composition(full,bad,arrays['rest'])
    except ValueError:rejected=True
    controls=dict(corrupted_stem_rejected=rejected,no_eligible_samples_yield_no_events=
        select_edges(full,rate,np.zeros(len(full),dtype=bool))==[])
    if not all(controls.values()):raise ValueError('Audio selection control survived')
    for root in (capture,normal):
        for p in root.iterdir():
            if p.is_file():sources[str(p)]=sha(p)
    for p in (Path(__file__),Path('tools/audit_postpublish_keyon.py'),Path('tools/audit_dsp_latency.py'),
        Path('tools/audit_noise_game.py'),Path('tools/capture_audio_stem.py'),Path('tools/review_native_transient_stems.py'),
        Path('tools/audit_gameplay_transients.py'),Path('tools/frame_audit.py')):sources[str(p)]=sha(p)
    dominant=sum(abs(e['contributions']['noise']['step'])>abs(e['contributions']['rest']['step']) for e in events)
    report=dict(passed=True,composition=mix,cadence=cadence,events=events,controls=controls,clips=clips,
        noise_larger_at_selected_sample=dominant,sources=sources,release_ready=False,pop_free_verified=False,
        physical_verified=False,scope=__doc__+' Native 32040Hz current route only. Largest separated steps '
        'are listening candidates, not a pop detector or NES equivalence test. No gain, time or phase fitting.')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Current native audio edges</title>'
        '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:2em auto}'
        'a{color:cyan}section{border-top:1px solid #567;margin-top:2em}img{width:256px;float:right;image-rendering:pixelated}'
        'audio{width:70%}svg{width:100%;height:150px}pre{white-space:pre-wrap}</style>'
        '<h1>Current game audio: exact noise/rest isolation</h1><p>Offline3032. No MiSTer or OBS changes. '
        'These are the twelve strongest half-second-separated gameplay sample steps, not twelve proven defects.</p>'
        f'<p>Noise contributes more than the rest of the mix at {dominant}/12 selected samples. '
        'The two stems reconstruct the entire mix within the measured integer rounding residual. '
        'All pictures/game state/input remain unchanged.</p><p>Native unnormalized one-second clips; '
        'waveforms share full-scale axes. No resampling, gain matching or local time alignment.</p>'
        '<details><summary>Measured packet cadence</summary><pre>'+html.escape(json.dumps(cadence,indent=2))+'</pre></details>'+
        ''.join(cards)+'<p><a href="report.json">Bound observations, actual DSP context and limitations</a></p>')
    for p,d in sources.items():
        if sha(Path(p))!=d:raise ValueError('Changed source '+p)
    report['artifacts']={p.name:sha(p) for p in out.iterdir() if p.is_file()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(noise_dominant=dominant,events=len(events),cadence={k:v for k,v in cadence.items() if k!='longest'},
        controls=controls)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('candidate','capture','normal','noise','rest','out'):p.add_argument('--'+k,type=Path,required=True)
    review(**vars(p.parse_args()))
