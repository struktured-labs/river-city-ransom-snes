"""Native physical transients and exact-command mixer stems, without local alignment.

Large steps are candidates for listening, not diagnosed pops. Cold replay, uncertain
physical sub-frame scheduling and DSP phase prevent sample-exact physical attribution.
"""
import argparse
from bisect import bisect_right
from collections import Counter, defaultdict
from html import escape
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from tools.audit_dsp_latency import dac_tick
from tools.audit_hardware_replay_gaps import register_context, waveform_svg
from tools.audit_main_display_latency import bound_report
from tools.audit_pulse_onset import load
from tools.audit_recorded_transients import measure, sensitivity
from tools.benchmark_report import sha
from tools.build_dispatch_packet_replay import replace


def read(path, rate):
    actual, pcm = wavfile.read(path)
    if actual != rate or pcm.dtype != np.int16 or pcm.ndim != 2 or pcm.shape[1] != 2:
        raise ValueError('Need untouched native stereo S16 PCM')
    return pcm


def composition(full, first, second):
    if (full.shape != first.shape or full.shape != second.shape or
            any(p.dtype != np.int16 or p.ndim != 2 or p.shape[1] != 2 for p in (full,first,second))):
        raise ValueError('Different stem lengths/formats')
    # This is an executed property of this non-clipping replay, not a universal
    # linear-mixer assumption: signed volume multiplication rounds each stem.
    residual = full.astype(np.int32)-first.astype(np.int32)-second.astype(np.int32)
    values, counts = np.unique(residual, return_counts=True)
    if not set(values).issubset({0, 1}):
        raise ValueError('Stems do not reconstruct the actual full mix')
    if not np.any(first) or not np.any(second):
        raise ValueError('Silent stem cannot qualify channel isolation')
    return dict(samples=int(residual.size), residual_counts={str(v):int(c) for v,c in zip(values,counts)})


def mapped_window(event, physical_rate, replay_rate, lag, timeline, radius=.02):
    if not np.isfinite(lag) or not timeline or radius <= 0:
        raise ValueError('Invalid fixed alignment/coverage')
    center = event['sample']/physical_rate-lag
    first, last = round((center-radius)*replay_rate), round((center+radius)*replay_rate)
    covered = timeline[0]['start_sample'] <= first < last <= timeline[-1]['end_sample']
    return dict(center_seconds=center, first=first, last=last, covered=covered,
                reason=None if covered else 'Outside emitted command coverage; not classified')


def steps_at_peak(arrays, first, last):
    if first < 1 or last > len(arrays['replay']) or last <= first:
        raise ValueError('Invalid native sample window')
    full = arrays['replay'].astype(np.int32)
    changes = np.abs(full[first:last]-full[first-1:last-1])
    offset, channel = np.unravel_index(changes.argmax(), changes.shape)
    sample = first+int(offset)
    details = {}
    for label, pcm in arrays.items():
        if pcm.shape != full.shape:
            raise ValueError('Different same-command replay lengths')
        data = pcm.astype(np.int32)
        details[label] = dict(before=int(data[sample-1,channel]), after=int(data[sample,channel]),
            signed_step=int(data[sample,channel]-data[sample-1,channel]),
            window_peak=int(np.abs(data[first:last]).max()),
            window_max_step=int(np.abs(data[first:last]-data[first-1:last-1]).max()))
    return dict(sample=sample, channel=int(channel), channels_at_identical_sample=details,
        scope='Largest replay full-mix step in the fixed +/-20ms window. This is NOT '
              'a waveform-phase match to the physical step. Every stem uses this exact sample.')


def same_core_load(observed, normal, fixture):
    a = bound_report(observed/'report.json')
    b = bound_report(normal/'report.json')
    cores = [{k:v for k,v in r['sources'].items() if k.endswith('.so')} for r in (a,b)]
    if len(cores[0]) != 1 or cores[0] != cores[1]:
        raise ValueError('Observer requires an actual same-core normal control')
    return load(observed, normal, fixture)


def compare_ready(writes, ready, newwrites, newready):
    if not ready or set(ready) != set(newready):
        raise ValueError('Missing synthesis completion')
    groups = []
    for rows in (writes,newwrites):
        group = defaultdict(list)
        for row in rows:
            group[row['packet']].append((row['register'],row['value']))
        groups.append(group)
    before, after = groups
    changes = []
    for packet in sorted(set(before)|set(after)):
        a,b = before[packet],after[packet]
        if a != b:
            changes.append(dict(packet=packet,baseline_writes=a,candidate_writes=b,
                removed=sum((Counter(a)-Counter(b)).values()),
                added=sum((Counter(b)-Counter(a)).values())))
    states = [dict(packet=p,registers={f'{i:02x}':[ready[p]['registers'][i],newready[p]['registers'][i]]
        for i in range(128) if ready[p]['registers'][i]!=newready[p]['registers'][i]})
        for p in sorted(ready) if ready[p]['registers']!=newready[p]['registers']]
    return dict(completions=len(ready), changed_ready_states=states, changed_write_sequences=changes,
        scope='Actual DSP register state at each packet ready signal, not internal oscillator phase. '
              'All changed per-packet write sequences retained, including timer maintenance writes.')


def build(review, hardware, decoded, fixture, normal, observed, noise, rest, triangle,
          nontriangle, candidate, candidate_fixture, candidate_normal, candidate_observed, out):
    if out.exists():
        raise ValueError('Fresh output required')
    prior = bound_report(review/'report.json')
    hw = bound_report(hardware/'report.json')
    spec = bound_report(fixture/'manifest.json')
    newer = bound_report(candidate_fixture/'manifest.json')
    meta = json.loads((candidate/'manifest.json').read_text())
    for source in (hardware/'report.json', decoded/'input.wav', fixture/'manifest.json'):
        if prior['sources'].get(str(source)) != sha(source):
            raise ValueError('Different physical episode or alignment source')
    if spec['source_rom_sha256'] != hw['diagnostic_rom_sha256']:
        raise ValueError('Different physical command source')
    stream = (fixture/'stream.bin').read_bytes()
    if stream != b''.join(b'\1'+bytes.fromhex(r['packet']) for r in hw['log']['records']):
        raise ValueError('Replay differs from captured packets')
    if (candidate_fixture/'stream.bin').read_bytes() != stream:
        raise ValueError('Candidate command stream differs')
    if sha(candidate/'native-cpu.sfc') != meta['rom_sha256']:
        raise ValueError('Unbound latest cartridge')
    at, size = meta['sweep_driver_rom_offset'], meta['sweep_driver_layout']['engine_bytes']
    engine = (candidate/'native-cpu.sfc').read_bytes()[at:at+size]
    if engine != (candidate_fixture/'engine.bin').read_bytes() or newer['engine_source_rom_sha256'] != meta['rom_sha256']:
        raise ValueError('Not latest cartridge engine')
    expected, dispatch = replace((fixture/'player.sfc').read_bytes(), (fixture/'engine.bin').read_bytes(),
        engine, meta['sweep_driver_layout'], meta['receiver_poll'])
    if expected != (candidate_fixture/'player.sfc').read_bytes():
        raise ValueError('Unrelated candidate fixture changes')
    obs, _, writes, ready = same_core_load(observed, normal, fixture)
    newobs, _, newwrites, newready = same_core_load(candidate_observed, candidate_normal, candidate_fixture)
    base_receipt = bound_report(normal/'report.json')
    new_receipt = bound_report(candidate_normal/'report.json')
    if ({k:v for k,v in base_receipt['sources'].items() if k.endswith('.so')} !=
            {k:v for k,v in new_receipt['sources'].items() if k.endswith('.so')}):
        raise ValueError('Engine comparison needs identical cores')
    # Reuse the fixed lag only if the new same-core control is byte-identical
    # to the replay on which that lag was established. Different-core evidence
    # alone does not qualify observer neutrality.
    prior_audio = [p for p in prior['sources'] if Path(p).name == 'audio.wav']
    prior_timeline = [p for p in prior['sources'] if Path(p).name == 'timeline.json']
    if (len(prior_audio) != 1 or len(prior_timeline) != 1 or
            prior['sources'][prior_audio[0]] != sha(normal/'audio.wav') or
            prior['sources'][prior_timeline[0]] != sha(normal/'timeline.json')):
        raise ValueError('Fixed-lag reference PCM/timeline changed')
    physical = read(decoded/'input.wav',48000)
    arrays = dict(replay=read(normal/'audio.wav',32040))
    sources = {str(p):sha(p) for p in (Path(__file__), review/'report.json', hardware/'report.json',
        decoded/'report.json', decoded/'input.wav', fixture/'manifest.json', fixture/'stream.bin',
        fixture/'player.sfc', candidate_fixture/'manifest.json', candidate_fixture/'player.sfc',
        candidate_fixture/'stream.bin', candidate/'manifest.json', candidate/'native-cpu.sfc')}
    for label, directory, mode in (('noise',noise,'noise'), ('rest',rest,'without-noise'),
                                 ('triangle',triangle,'triangle'), ('nontriangle',nontriangle,'without-triangle')):
        binding = bound_report(directory/'stem.json')
        if (binding['mode'] != mode or not all(binding['nonaudio_equal'].values()) or
                binding['sources'].get(str(normal/'report.json')) != sha(normal/'report.json')):
            raise ValueError('Wrong stem or same-core control')
        arrays[label] = read(directory/'audio.wav',32040)
        for p in (directory/'stem.json', directory/'audio.wav'):
            sources[str(p)] = sha(p)
    compositions = dict(noise=composition(arrays['replay'],arrays['noise'],arrays['rest']),
                        triangle=composition(arrays['replay'],arrays['triangle'],arrays['nontriangle']))
    arrays['latest'] = read(candidate_normal/'audio.wav',32040)
    timeline = json.loads((normal/'timeline.json').read_text())
    changed_timeline = json.loads((candidate_normal/'timeline.json').read_text())
    if len(timeline) != len(changed_timeline):
        raise ValueError('Missing candidate packets')
    timing = {key:sum(a[key]!=b[key] for a,b in zip(timeline,changed_timeline)) for key in timeline[0]}
    if any(timing[k] for k in ('source_frame','host_frame','packets','packet')):
        raise ValueError('Candidate altered command contents/frame scheduling')
    for directory in (normal,observed,candidate_normal,candidate_observed):
        for name in ('report.json','timeline.json','audio.wav','memory.ram','last.png'):
            p = directory/name
            sources[str(p)] = sha(p)
        if (directory/'onset-observer.json').exists():
            sources[str(directory/'onset-observer.json')] = sha(directory/'onset-observer.json')
    lag = prior['alignment']['offset_seconds']
    stats = measure(physical,48000,12)
    controls = sensitivity(physical,48000)
    if not all(controls.values()):
        raise ValueError('Transient negative controls failed')
    out.mkdir(parents=True)
    events, cards, clips = [], [], []
    ticks = [ready[i]['tick'] for i in range(1,len(ready)+1)]
    for i, event in enumerate(stats['strongest_separated_events'],1):
        window = mapped_window(event,48000,32040,lag,timeline)
        item = dict(physical=event,mapped=window,classified_as_pop=False)
        card = f'<section><h2>#{i}: physical {event["seconds"]:.6f}s; step {event["step"]}</h2>'
        def clip(label, pcm, rate, first, last, source):
            nonlocal card
            name = f'event-{i:02d}-{label}.wav'
            first, last = max(0,first), min(len(pcm),last)
            wavfile.write(out/name,rate,pcm[first:last])
            clips.append(dict(file=name,source=str(source),first=first,last=last,rate=rate))
            card += f'<p>{escape(label)} — native {rate}Hz</p><audio controls preload="none" src="{name}"></audio>'
        clip('physical',physical,48000,event['sample']-24000,event['sample']+24000,decoded/'input.wav')
        if window['covered']:
            item['replay_peak'] = steps_at_peak(arrays,window['first'],window['last'])
            index = bisect_right(ticks,dac_tick(item['replay_peak']['sample']))
            item['nearby_packets'] = hw['log']['records'][max(0,index-2):min(len(ticks),index+2)]
            item['dsp'] = register_context(writes,item['replay_peak']['sample'])
            center = round(window['center_seconds']*32040)
            dirs = dict(replay=normal,noise=noise,rest=rest,triangle=triangle,nontriangle=nontriangle,latest=candidate_normal)
            for label, pcm in arrays.items():
                clip(label,pcm,32040,center-16020,center+16020,dirs[label]/'audio.wav')
            for label, pair in (('physical-replay', [('Physical',physical,48000,32768,event['seconds']),
                ('Cold replay',arrays['replay'],32040,32768,window['center_seconds'])]),
                ('noise-rest', [(k,arrays[k],32040,32768,window['center_seconds']) for k in ('noise','rest')]),
                ('triangle-rest', [(k,arrays[k],32040,32768,window['center_seconds']) for k in ('triangle','nontriangle')])):
                name = f'event-{i:02d}-{label}.svg'
                (out/name).write_text(waveform_svg(pair,limit=.25))
                card += f'<img src="{name}" loading="lazy">'
            card += '<pre>'+escape(json.dumps(item['replay_peak'],indent=2))+'</pre>'
        else:
            card += '<p>'+window['reason']+'</p>'
        cards.append(card+'</section>')
        events.append(item)
    def summary(o):
        return {k:o[k] for k in ('observer_neutral','raw_dac_identical','received_packets','eligible',
                                 'wrong_first_pitch','stale_nonzero_onsets')}
    comparison = dict(dispatch=dispatch, baseline=summary(obs),candidate=summary(newobs),
        baseline_dsp_writes=len(writes),candidate_dsp_writes=len(newwrites), timeline_differences=timing,
        synthesis=compare_ready(writes,ready,newwrites,newready),
        callback_boundary_max_delta=max(abs(a[k]-b[k]) for a,b in zip(timeline,changed_timeline)
            for k in ('start_sample','end_sample')), total_pcm_samples_equal=arrays['replay'].shape==arrays['latest'].shape,
        pcm_equal=bool(np.array_equal(arrays['replay'],arrays['latest'])),
        scope='Exact captured commands and host frame schedule; receiver poll timing intentionally differs. '
              'DSP writes, callback boundaries and waveform may change; no audible-improvement claim.')
    page = '<!doctype html><meta charset="utf-8"><title>Native transient stems</title><style>body{max-width:1100px;margin:30px auto;background:#101821;color:#eee;font:17px system-ui}a{color:#9df}img{width:100%}audio{width:100%;max-width:600px}pre{white-space:pre-wrap}section{border-top:1px solid #567;margin-top:35px}</style>'
    page += '<h1>Gameplay transients: unchanged physical PCM and exact-command stems</h1>'
    page += f'<p>Top twelve separated physical sample steps; one existing fixed lag of {lag}s. No per-event fitting, normalization or resampling. '+escape(__doc__)+'</p>'
    page += '<p>Noise+rest and triangle+rest reconstruct every replay sample to integer rounding (0 or 1). These are host-mixer stems, not isolated physical channels. Stem values at a replay peak share one exact sample; the physical waveform does not.</p>'
    compact = {k:v for k,v in comparison.items() if k != 'synthesis'}
    compact['synthesis'] = dict(completions=comparison['synthesis']['completions'],
        changed_ready_states=len(comparison['synthesis']['changed_ready_states']),
        changed_write_sequences=len(comparison['synthesis']['changed_write_sequences']))
    page += '<h2>Latest speed candidate engine</h2><pre>'+escape(json.dumps(compact,indent=2))+'</pre>'
    page += ''.join(cards)+'<p><a href="report.json">All measurements, command context and hashes</a></p>'
    (out/'index.html').write_text(page)
    for name in ('audit_dsp_latency.py','audit_hardware_replay_gaps.py','audit_main_display_latency.py',
                 'audit_pulse_onset.py','audit_recorded_transients.py','audit_recording_audio_path.py',
                 'build_dispatch_packet_replay.py','build_receiver_dispatch_trial.py','replay_packet_stem.py'):
        p = Path('tools')/name
        sources[str(p)] = sha(p)
    result = dict(scope=__doc__, fixed_lag_seconds=lag, events=events, compositions=compositions,
        comparison=comparison, controls=controls, clips=clips, sources=sources,
        pop_free_verified=False, physical_causality_proven=False, release_ready=False,
        artifacts={p.name:sha(p) for p in out.iterdir()})
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),events=len(events),covered=sum(e['mapped']['covered'] for e in events),
        compositions=compositions,comparison=compact)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('review','hardware','decoded','fixture','normal','observed','noise','rest','triangle',
                 'nontriangle','candidate','candidate-fixture','candidate-normal','candidate-observed','out'):
        p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
