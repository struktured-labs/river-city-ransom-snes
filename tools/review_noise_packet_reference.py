"""Compare current SPC noise with an executed, state-derived NES reference.

Frozen physical-event selection, whole source-frame windows, native sample rates.
No local alignment, normalization, resampling, or automatic pop/fidelity verdict.
"""
import argparse
from collections import defaultdict
import html
import json
from pathlib import Path
import shutil

import numpy as np
from scipy.io import wavfile

from tools.audit_main_display_latency import bound_report
from tools.audit_noise_game import spectrum
from tools.audit_recorded_transients import waveform_svg
from tools.benchmark_report import sha
from tools.build_noise_packet_reference import stimulus
from tools.review_native_transient_stems import mapped_window, read


def validate_timeline(rows, count, samples):
    if [r['source_frame'] for r in rows] != list(range(1, count+1)):
        raise ValueError('Missing or reordered reference frames')
    if any(not 0 <= r['start_sample'] < r['end_sample'] <= samples for r in rows):
        raise ValueError('Invalid native sample bounds')
    if any(a['end_sample'] != b['start_sample'] for a,b in zip(rows,rows[1:])):
        raise ValueError('Noncontiguous reference samples')


def frame_window(rows, first, last):
    if not rows or not rows[0]['start_sample'] <= first < last <= rows[-1]['end_sample']:
        raise ValueError('Selection outside emitted-command coverage')
    selected = [r['source_frame'] for r in rows if r['start_sample'] < last and r['end_sample'] > first]
    return selected[0], selected[-1]


def measure(pcm, rate, first, last):
    if pcm.dtype != np.int16 or pcm.ndim != 2 or pcm.shape[1] != 2 or not 0 < first < last <= len(pcm):
        raise ValueError('Invalid native PCM/window')
    x = pcm[first:last].astype(np.int32)
    steps = np.abs(x-pcm[first-1:last-1].astype(np.int32))
    peak, maximum = int(np.abs(x).max()), int(steps.max())
    return dict(first_sample=first,last_sample=last,rate=rate,peak=peak,
        max_step=maximum,step_to_peak=maximum/peak if peak else None,
        clipped_samples=int(np.count_nonzero(np.abs(x)>=32767)),
        mean=x.mean(axis=0).tolist(),rms=np.sqrt(np.mean(x.astype(float)**2,axis=0)).tolist(),
        spectral_centroid_hz=spectrum(x,rate) if np.any(x != x[0]) else None)


def build(reference, stem, normal, fixture, selection, candidate, out):
    if out.exists(): raise ValueError('Fresh review required')
    reports = {name:bound_report(path) for name,path in (
        ('nes',reference/'report.json'),('stem',stem/'stem.json'),
        ('normal',normal/'report.json'),('fixture',fixture/'manifest.json'),
        ('selection',selection/'report.json'))}
    meta = json.loads((candidate/'manifest.json').read_text())
    engine = (candidate/'native-cpu.sfc').read_bytes()
    at,size = meta['sweep_driver_rom_offset'],meta['sweep_driver_layout']['engine_bytes']
    if (sha(candidate/'native-cpu.sfc') != meta['rom_sha256'] or
            engine[at:at+size] != (fixture/'engine.bin').read_bytes() or
            reports['nes']['source_spc_sha256'] != meta['spc_sha256']):
        raise ValueError('Reference does not use current cartridge engine')
    if (reports['stem']['mode'] != 'noise' or not all(reports['stem']['nonaudio_equal'].values()) or
            reports['stem']['sources'].get(str(normal/'report.json')) != sha(normal/'report.json') or
            reports['normal']['sources'].get(str(fixture/'player.sfc')) != reports['fixture']['rom_sha256'] or
            reports['nes']['sources'].get(str(fixture/'stream.bin')) != sha(fixture/'stream.bin')):
        raise ValueError('Different fixture or unqualified mixer isolation')
    # Both the normal replay and fixed selection must be the retained current
    # engine arm. Do not silently borrow another stream or re-fit a physical lag.
    if reports['selection']['sources'].get(str(normal/'audio.wav')) != sha(normal/'audio.wav'):
        raise ValueError('Different physical selection replay')
    stream = (fixture/'stream.bin').read_bytes()
    grouped = stimulus(stream)
    packets = [stream[i+1:i+24] for i in range(0,len(stream),24)]
    expected = bytes(v for row in grouped for v in [len(row),*[v for pair in row for v in pair]])
    if expected != (reference/'stimulus.bin').read_bytes():
        raise ValueError('Changed NES stimulus')
    arrays = dict(nes=read(reference/'audio.wav',48000),snes=read(stem/'audio.wav',32040))
    rows = {k:json.loads((p/'timeline.json').read_text()) for k,p in (('nes',reference),('snes',stem))}
    rates = dict(nes=48000,snes=32040)
    for k in rows: validate_timeline(rows[k],len(packets),len(arrays[k]))
    if any(r['apu_status'] != 8 for r in rows['nes']):
        raise ValueError('NES length-held noise did not remain enabled')
    if [r['packet'] for r in rows['snes']] != [p.hex() for p in packets]:
        raise ValueError('Different executed SNES packet sequence')
    out.mkdir(parents=True)
    sources = {str(p):sha(p) for p in (Path(__file__),Path('tools/audit_noise_game.py'),
        Path('tools/audit_recorded_transients.py'),Path('tools/build_noise_packet_reference.py'),
        Path('tools/review_native_transient_stems.py'),Path('tools/audit_main_display_latency.py'),
        fixture/'engine.bin',fixture/'stream.bin',candidate/'manifest.json',candidate/'native-cpu.sfc',
        reference/'stimulus.bin',reference/'timeline.json',reference/'audio.wav',
        stem/'timeline.json',stem/'audio.wav')}
    for name,path in (('nes',reference/'report.json'),('stem',stem/'stem.json'),
        ('normal',normal/'report.json'),('fixture',fixture/'manifest.json'),('selection',selection/'report.json')):
        sources[str(path)]=sha(path)
        sources.update(reports[name]['sources'])
    clips,events,cards = [],[],[]
    for index,event in enumerate(reports['selection']['events'],1):
        window = mapped_window(event['physical'],48000,32040,
            reports['selection']['fixed_lag_seconds'],rows['snes'])
        item = dict(physical_event=event['physical'],mapped=window,classified_as_pop=False)
        if not window['covered']:
            events.append(item);continue
        first,last=frame_window(rows['snes'],window['first'],window['last'])
        item.update(first_frame=first,last_frame=last,
            noise_states=[dict(frame=f,control=packets[f-1][12],period=packets[f-1][14]) for f in range(first,last+1)],
            metrics={})
        card=f'<section><h2>Event {index}: physical {event["physical"]["seconds"]:.6f}s</h2><p>Whole source frames {first}–{last}. Not phase-aligned.</p>'
        for system in ('nes','snes'):
            a,b=rows[system][first-1]['start_sample'],rows[system][last-1]['end_sample']
            item['metrics'][system]=measure(arrays[system],rates[system],a,b)
            # Listening context is a fixed +/-15 source frames, not a cropped peak.
            c=rows[system][max(0,first-16)]['start_sample']
            d=rows[system][min(len(packets),last+15)-1]['end_sample']
            name=f'event-{index:02}-{system}.wav'
            wavfile.write(out/name,rates[system],arrays[system][c:d])
            clips.append(dict(file=name,system=system,first=c,last=d))
            svg=f'event-{index:02}-{system}.svg'
            (out/svg).write_text(waveform_svg(arrays[system][a:b]).replace(
                '<svg ', '<svg xmlns="http://www.w3.org/2000/svg" ', 1))
            card+=f'<h3>{system.upper()}</h3><audio controls src="{name}"></audio><img src="{svg}">'
        card+='<pre>'+html.escape(json.dumps(item['metrics'],indent=2))+'</pre></section>'
        cards.append(card);events.append(item)
    # Report every state-selected stable frame, not only the twelve transients.
    steady=[];groups=defaultdict(list)
    keys=[(p[12],p[14]&15) for p in packets]
    for index in range(2,len(packets)-2):
        if keys[index][0]&15 < 2 or len(set(keys[index-2:index+3])) != 1:continue
        item=dict(frame=index+1,control=keys[index][0],period=keys[index][1])
        for system in ('nes','snes'):
            row=rows[system][index]; trim=(row['end_sample']-row['start_sample'])//5
            item[system]=measure(arrays[system],rates[system],row['start_sample']+trim,row['end_sample']-trim)
        steady.append(item);groups[item['period']].append(item)
    summaries={str(period):dict(frames=len(items),**{system:dict(
        centroid_mean_hz=float(np.mean([v[system]['spectral_centroid_hz'] for v in items])),
        mean_step_to_peak=float(np.mean([v[system]['step_to_peak'] for v in items]))) for system in ('nes','snes')})
        for period,items in groups.items()}
    for system,directory in (('nes',reference),('snes',stem)):
        shutil.copyfile(directory/'audio.wav',out/(system+'-full.wav'))
    report=dict(events=events,steady_frames=steady,steady_by_period=summaries,clips=clips,
        reference_scope=reports['nes']['scope'],source_frames=len(packets),
        spc_sha256=meta['spc_sha256'],executed_negative_control=reports['nes']['executed_negative_control'],
        physical_causality_proven=False,pop_free_verified=False,release_ready=False,sources=sources)
    page='<!doctype html><meta charset="utf-8"><title>Current noise / NES state reference</title><style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1000px;margin:30px auto}a{color:#8df}img{width:100%}pre{white-space:pre-wrap}section{border-top:1px solid #789;margin-top:30px}</style>'
    page+='<h1>Current SNES noise vs executed NES state reference</h1><p>'+html.escape(__doc__)+'</p><p>'+html.escape(reports['nes']['scope'])+'</p>'
    page+='<p>All listening files are untouched native sample slices. Waveforms use full-scale axes and whole-frame windows; listening context extends 15 frames each side. No waveform equality or pop-free claim.</p>'
    page+='<p><a href="nes-full.wav">Full NES reference</a> · <a href="snes-full.wav">Full current SPC noise</a> · <a href="report.json">Every state, selection and hash</a></p>'
    page+='<h2>State-selected steady frames</h2><p>Requires five consecutive identical volume/period states, volume at least 2. '
    page+=f'{len(steady)} frames qualify. An empty selection is not a steady-tone pass.</p><pre>'+html.escape(json.dumps(summaries,indent=2))+'</pre>'
    page+='<p>Uncovered physical events: '+', '.join(str(i+1) for i,e in enumerate(events) if not e['mapped']['covered'])+'</p>'+''.join(cards)
    (out/'index.html').write_text(page)
    report['artifacts']={p.name:sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(events=len(events),covered=sum(e['mapped']['covered'] for e in events),
        steady_by_period=summaries,pop_free_verified=False)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('reference','stem','normal','fixture','selection','candidate','out'):
        p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
