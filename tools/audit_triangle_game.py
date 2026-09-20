"""Compare exact-frame equal-command game windows, full mix and triangle stem.

No phase/time/gain fitting. Selection is explicit; unmatched windows fail.
This is not a full-route equality or subjective click-free certification.
"""
import argparse
from collections import Counter, defaultdict
import html
import json
from pathlib import Path
import wave

import numpy as np

from tools.audit_stimulus_audio import metrics, verify_sources
from tools.benchmark_report import sha, verify_capture
from tools.capture_audio_stem import options_for


def command_window(packets, first, last):
    by_frame = defaultdict(list)
    prior = -1
    for packet in packets:
        frame = packet['frame']; data = bytes.fromhex(packet['bytes'])
        if frame < prior or len(data) != 23:
            raise ValueError('Invalid packet order/width')
        prior = frame
        by_frame[frame].append(data)
    # Require every frame: do not infer omitted transport or select isolated
    # favorable events from a divergent script. Include previous packet state.
    if any(len(by_frame[f]) != 1 for f in range(first-2, last+3)):
        raise ValueError('Need exactly one packet per guarded source frame')
    return {f:by_frame[f][0] for f in range(first-2,last+3)}


def edges(commands, first, last):
    found = []
    def active(data): return bool(data[21]&4 and data[8]&127)
    for f in range(first,last+1):
        a,b=commands[f-1],commands[f]
        if (a[22]|b[22])&32 or a[17] or b[17] or not (a[8]&128 and b[8]&128):
            raise ValueError('Unsupported triangle/mixing mode in window')
        if active(a) != active(b):
            found.append(dict(frame=f,kind='on' if active(b) else 'off',
                              before=a.hex(),after=b.hex()))
    if {e['kind'] for e in found} != {'on','off'}:
        raise ValueError('Need actual on and off events')
    return found


def read_audio(root):
    with wave.open(str(root/'audio.wav')) as f:
        if f.getnchannels()!=2 or f.getsampwidth()!=2:
            raise ValueError('Need stereo PCM16')
        return f.getframerate(),np.frombuffer(f.readframes(f.getnframes()),'<i2').reshape(-1,2)


def section(pcm, rows, first, last):
    selected=rows[first-1:last]
    if [r['frame'] for r in selected] != list(range(first,last+1)):
        raise ValueError('Missing selected source frames')
    start=selected[0]['audio_start_sample'];end=start
    for row in selected:
        if row['audio_start_sample']!=end or row['audio']['samples']<=0:
            raise ValueError('Discontinuous audio callbacks')
        end+=row['audio']['samples']
    if not 0<=start<end<=len(pcm):raise ValueError('Incomplete PCM window')
    return pcm[start:end],start,end


def audit(manifest,first,last,out):
    config=json.loads(manifest.read_text())
    if set(config)!={'baseline','candidate'}:raise ValueError('Need both builds')
    loaded={};sources=[manifest,Path(__file__),Path('tools/capture_audio_stem.py'),
        Path('tools/audit_stimulus_audio.py'),Path('tools/benchmark_report.py')]
    for name,entry in config.items():
        normal,stem,proof=(Path(entry[k]) for k in ('normal','stem','provenance'))
        receipt,rows=verify_capture(normal);stem_receipt,stem_rows=verify_capture(stem)
        provenance=verify_sources(proof/'report.json')
        if (not receipt['capture_complete'] or not stem_receipt['capture_complete'] or
            receipt['rom_sha256'] != stem_receipt['rom_sha256'] or
            receipt['rom_sha256'] != provenance['rom_sha256'] or
            receipt['audio_sha256'] != provenance['audio_sha256'] or
            provenance['sources'].get(str(normal/'capture.json')) != sha(normal/'capture.json')):
            raise ValueError('Unbound or incomplete game/provenance/stem')
        strip=lambda r:{k:v for k,v in r.items() if k not in ('audio','audio_start_sample')}
        if len(rows)!=len(stem_rows) or any(strip(a)!=strip(b) for a,b in zip(rows,stem_rows)):
            raise ValueError('Triangle isolation changed gameplay')
        expected={k.decode():v.decode() for k,v in options_for('snes','triangle').items()}
        if (stem_receipt['audio_stem']['options_queried']!=expected or
            stem_receipt['audio_stem']['wrapper_sha256']!=sha(Path('tools/capture_audio_stem.py'))):
            raise ValueError('Unverified triangle mixer options')
        packets=json.loads((proof/'bus-report.json').read_text())['packets']
        commands=command_window(packets,first,last)
        loaded[name]=dict(commands=commands,audio={},rom_sha256=receipt['rom_sha256'],
                          isolation_gameplay_neutral=True)
        for mode,root,rr in (('mix',normal,rows),('triangle',stem,stem_rows)):
            rate,pcm=read_audio(root)
            loaded[name]['audio'][mode]=(rate,pcm,rr)
            sources.extend(root/p for p in ('capture.json','timeline.json','audio.wav'))
        sources.extend([proof/'report.json',proof/'bus-report.json'])
    if loaded['baseline']['commands'] != loaded['candidate']['commands']:
        raise ValueError('Source-frame packet commands differ; no rematching allowed')
    events=edges(loaded['baseline']['commands'],first,last)
    out.mkdir(parents=True,exist_ok=False)
    systems={};cards=[]
    for name,run in loaded.items():
        systems[name]={}
        for mode,(rate,pcm,rows) in run['audio'].items():
            window,start,end=section(pcm,rows,first,last)
            path=out/f'{name}-{mode}.wav'
            with wave.open(str(path),'wb') as f:
                f.setnchannels(2);f.setsampwidth(2);f.setframerate(rate);f.writeframes(window.tobytes())
            systems[name][mode]=dict(rate=rate,first_sample=start,end_sample=end,**metrics(window),events=[])
            for event in events:
                clip,a,b=section(pcm,rows,event['frame']-1,event['frame']+1)
                systems[name][mode]['events'].append(dict(**event,first_sample=a,end_sample=b,**metrics(clip)))
            points=[]
            for i,part in enumerate(np.array_split(window[:,0],min(1000,len(window)))):
                points.append(f'<path d="M{i},{100-int(part.max())*95/32768:.2f}V{100-int(part.min())*95/32768:.2f}"/>')
            cards.append(f'<h2>{name} · {mode}</h2><audio controls src="{path.name}"></audio>'
                '<svg viewBox="0 0 1000 200"><g stroke="#6df">'+''.join(points)+'</g></svg>')
            sources.append(path)
    comparisons={}
    for mode in ('mix','triangle'):
        pairs=[]
        for a,b in zip(systems['baseline'][mode]['events'],systems['candidate'][mode]['events']):
            pairs.append(dict(frame=a['frame'],kind=a['kind'],baseline_step=a['max_step'],candidate_step=b['max_step']))
        comparisons[mode]=dict(events=pairs,
            improved=sum(e['candidate_step']<e['baseline_step'] for e in pairs),
            worse=sum(e['candidate_step']>e['baseline_step'] for e in pairs),
            equal=sum(e['candidate_step']==e['baseline_step'] for e in pairs))
    report=dict(first=first,last=last,equal_guarded_packets=last-first+5,
        event_counts=dict(Counter(e['kind'] for e in events)),systems=systems,comparisons=comparisons,
        roms={n:v['rom_sha256'] for n,v in loaded.items()},
        stems_gameplay_neutral=True,release_ready=False,pop_free_verified=False,
        sources={str(p):sha(p) for p in sources},
        scope='Explicit complete frame window with identical actual received packet bytes on every guarded '
              'frame. All triangle enable/linear-control boundaries retained; native PCM amplitude and '
              'sample rates, no gain/phase/time fit. Mixer isolation is gameplay-neutral. Earlier histories '
              'and oscillator phases may differ; no full-route equal-work or NES fidelity claim.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    table=''.join(f'<tr><td>{mode}</td><td>{c["improved"]}</td><td>{c["worse"]}</td><td>{c["equal"]}</td></tr>' for mode,c in comparisons.items())
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Game triangle boundary comparison</title>'
        '<style>body{background:#101821;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto;padding:15px}a{color:#9df}audio,svg{width:100%}td,th{padding:8px;border:1px solid #567}</style>'
        f'<h1>Game frames {first}–{last}: identical packet commands</h1><p>'+html.escape(report['scope'])+'</p>'
        '<p><a href="report.json">All events, packet bytes and hashes</a>. Not deployed to Rival.</p>'
        '<table><tr><th>Signal</th><th>Smaller boundary step</th><th>Larger</th><th>Equal</th></tr>'+table+'</table>'
        '<p>Each boundary measurement includes one frame before and after; all results retained. '
        'Full-window waveforms show signed-16-bit full scale; audio remains stereo and unnormalized.</p>'+''.join(cards))
    print(json.dumps(dict(event_counts=report['event_counts'],comparisons={m:{k:v for k,v in c.items() if k!='events'} for m,c in comparisons.items()})))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','out'):p.add_argument('--'+name,required=True,type=Path)
    for name in ('first','last'):p.add_argument('--'+name,required=True,type=int)
    audit(**vars(p.parse_args()))
