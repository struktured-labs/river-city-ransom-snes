"""Reconstruct selected native DAC samples from actual DSP source and mixer phases.

Local replay diagnosis, not physical phase matching or a perceptual pop verdict.
"""
import argparse
from bisect import bisect_left
from collections import defaultdict
import csv
from html import escape
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from tools.audit_main_display_latency import bound_report
from tools.audit_pulse_pitch import pitch_updates, sample_expectation
from tools.benchmark_report import sha
from tools.capture_voice_edges import windows
from tools.review_native_transient_stems import same_core_load


FIELDS = {
    'N': 'sample tick packet before after flg',
    'S': 'sample tick packet voice raw env output noise non pitch regpitch delay flg srcn brr interp adsr gain previous_delay',
    'V': 'sample tick packet voice channel output volume amp before enabled',
    'M': 'sample tick packet channel main volume echo evolume output flg',
}


def signed(value, bits=16):
    return (value+(1 << (bits-1))) % (1 << bits)-(1 << (bits-1))


def clamp(value):
    return max(-32768,min(32767,value))


def noise_next(value):
    if not 0 <= value <= 32767:
        raise ValueError('Invalid 15-bit noise state')
    return (((value << 13) ^ (value << 14)) & 0x4000) ^ (value >> 1)


def parse(path, selected):
    expected = {i for a,b in selected for i in range(a,b)}
    groups = defaultdict(list)
    previous_tick = -1
    with path.open() as source:
        for raw in csv.reader(source):
            if not raw or raw[0] not in FIELDS or len(raw) != len(FIELDS[raw[0]].split())+1:
                raise ValueError('Malformed voice edge record')
            row = dict(zip(FIELDS[raw[0]].split(),map(int,raw[1:])),kind=raw[0])
            if row['sample'] not in expected or row['tick'] < previous_tick:
                raise ValueError('Out-of-window or reordered voice record')
            groups[row['sample']].append(row)
            previous_tick = row['tick']
    if set(groups) != expected:
        raise ValueError('Missing selected DAC samples')
    return groups


def registers(writes):
    ticks, values = defaultdict(list),defaultdict(list)
    for w in writes:
        ticks[w['register']].append(w['tick'])
        values[w['register']].append(w['value'])
    def read(address,tick):
        i = bisect_left(ticks[address],tick)-1
        if i < 0:
            raise ValueError('Selected voice state precedes initialized DSP register')
        return values[address][i]
    return read


def validate_group(sample, records, pcm, register):
    noise, sources, voices, mixes = [], {}, {}, {}
    for row in records:
        if row['sample'] != sample:
            raise ValueError('Wrong DAC sample')
        kind = row['kind']
        if kind == 'N':
            noise.append(row); expected_tick = 32*sample-1
        elif kind == 'S':
            v = row['voice']
            if v not in range(8) or v in sources:
                raise ValueError('Invalid/duplicate source voice')
            sources[v] = row; expected_tick = 32*sample+3*v-1
        elif kind == 'V':
            v,ch = row['voice'],row['channel']
            if v not in range(8) or ch not in (0,1) or (v,ch) in voices:
                raise ValueError('Invalid/duplicate mixer voice')
            voices[v,ch] = row; expected_tick = 32*sample+3*v+ch
        elif kind == 'M':
            ch = row['channel']
            if ch not in (0,1) or ch in mixes:
                raise ValueError('Invalid/duplicate final mix')
            mixes[ch] = row; expected_tick = 32*sample+27+ch
        else:
            raise ValueError('Unknown voice event')
        if row['tick'] != expected_tick:
            raise ValueError('Wrong DSP read/mix phase')
    if len(noise)!=1 or len(sources)!=8 or len(voices)!=16 or len(mixes)!=2:
        raise ValueError('Incomplete all-voice DAC coverage')
    n = noise[0]
    if n['flg'] != register(0x6c,n['tick']) or n['after'] not in (n['before'],noise_next(n['before'])):
        raise ValueError('Unexplained noise transition')
    for v,s in sources.items():
        if (not 0<=s['env']<=2047 or not -32768<=s['raw']<=32767 or
                s['output'] != ((s['raw']*s['env']) >> 11 & ~1) or
                s['noise'] != n['after'] or s['non'] != register(0x3d,32*sample-3)):
            raise ValueError('Unexplained source envelope/noise latch')
        if (s['flg']!=register(0x6c,s['tick']) or s['adsr']!=register(16*v+5,s['tick']) or
                s['gain']!=register(16*v+7,s['tick']) or s['srcn']!=register(16*v+4,s['tick']) or
                s['regpitch']!=(register(16*v+2,s['tick']) | ((register(16*v+3,s['tick'])&63)<<8)) or
                not 0<=s['delay']<=5 or not 0<=s['previous_delay']<=5):
            raise ValueError('Unexplained source control snapshot')
        if s['non'] & (1 << v) and s['raw'] != signed(n['after']*2):
            raise ValueError('Noise source differs from actual LFSR')
    amplitudes = {}
    for ch in (0,1):
        total = 0
        for v in range(8):
            row = voices[v,ch]
            if row['enabled'] != 1 or row['output'] != sources[v]['output']:
                raise ValueError('Muted or changed voice output')
            volume = signed(register(16*v+ch,row['tick']),8)
            amp = sources[v]['output']*volume >> 7
            if row['volume'] != volume or row['amp'] != amp or row['before'] != total:
                raise ValueError('Unexplained voice mix arithmetic/order')
            amplitudes[v,ch] = amp
            total = clamp(total+amp)
        mix = mixes[ch]
        volume = signed(register(0x0c+16*ch,mix['tick']),8)
        evolume = signed(register(0x2c+16*ch,mix['tick']),8)
        expected = clamp(signed(total*volume >> 7)+signed(mix['echo']*evolume >> 7))
        if (mix['main']!=total or mix['volume']!=volume or mix['evolume']!=evolume or
                mix['output']!=expected or mix['flg']!=register(0x6c,mix['tick'])):
            raise ValueError('Unexplained master/echo mixing')
        if register(0x6c,32*sample+28)&0x40:
            expected = 0
        if expected != int(pcm[ch]):
            raise ValueError('Reconstructed voice mix differs from native DAC')
    return dict(noise=n,sources=sources,voices=voices,mixes=mixes,amplitudes=amplitudes)


def audit(review, normal, observed, fixture, out):
    if out.exists():
        raise ValueError('Fresh evidence required')
    prior = bound_report(review/'report.json')
    binding = bound_report(observed/'voice-edge-observer.json')
    if binding['sources'].get(str(review/'report.json')) != sha(review/'report.json') or binding['windows'] != windows(prior):
        raise ValueError('Different reviewed edge selection')
    onset,_,writes,_ = same_core_load(observed,normal,fixture)
    # These are the recorded-engine peaks, not the newer engine's PCM peaks.
    old_audio = [p for p in prior['sources'] if 'native-onset-normal-' in p and p.endswith('/audio.wav')]
    if len(old_audio)!=1 or sha(normal/'audio.wav')!=prior['sources'][old_audio[0]]:
        raise ValueError('Changed native replay waveform; old peaks do not apply')
    rate,pcm = wavfile.read(normal/'audio.wav')
    if rate!=32040 or pcm.dtype!=np.int16:
        raise ValueError('Wrong native replay PCM')
    trace = Path(binding['trace'])
    groups = parse(trace,binding['windows'])
    register = registers(writes)
    updates = [pitch_updates(writes,v) for v in (0,1)]
    tables = [([u['low']['tick'] for u in us],[u['high']['tick'] for u in us],
               [u['low']['value'] for u in us],[u['high']['value'] for u in us]) for us in updates]
    validated, split, noise_changes = {}, [], 0
    for sample,records in sorted(groups.items()):
        r = validate_group(sample,records,pcm[sample],register)
        previous = validated.get(sample-1)
        if previous and previous['noise']['after'] != r['noise']['before']:
            raise ValueError('Discontinuous observed noise history')
        noise_changes += r['noise']['before'] != r['noise']['after']
        for voice in (0,1):
            s = r['sources'][voice]
            if register(0x2d,32*sample-4)&(1 << voice):
                raise ValueError('Pitch modulation needs a different oracle')
            expected = sample_expectation(32*sample+3*voice,voice,s['previous_delay'],updates[voice],*tables[voice])
            if s['pitch'] != expected['expected']:
                raise ValueError('Unexplained actual pulse pitch latch')
            if expected['split_byte']:
                split.append(dict(sample=sample,voice=voice,pitch=s['pitch'],output=s['output'],**expected))
        validated[sample] = r
    noise_path = next(p for p in prior['sources'] if p.endswith('/audio.wav') and 'native-noise-stem-' in p)
    _,noise_pcm = wavfile.read(noise_path)
    # Exact isolated channel cross-check, not just reconstruction of fields
    # emitted by the new observer. Gameplay echo volume must actually be zero.
    for sample,r in validated.items():
        for ch in (0,1):
            m = r['mixes'][ch]
            if m['evolume'] or register(0x6c,32*sample+28)&0x40:
                raise ValueError('Noise-only comparison requires unmuted zero echo volume')
            if int(noise_pcm[sample,ch]) != signed(r['amplitudes'][3,ch]*m['volume'] >> 7):
                raise ValueError('Observed noise voice differs from independent mixer stem')
    events = []
    for event in prior['events']:
        if not event['mapped']['covered']:
            continue
        peak = event['replay_peak']; sample,ch = peak['sample'],peak['channel']
        a,b = validated[sample-1],validated[sample]
        channels = []
        for v in range(4):
            before,after = a['sources'][v],b['sources'][v]
            restarts = [e for e in onset['events'] if e['voice']==v and
                        0 <= after['tick']-e['tick'] <= 192]
            channels.append(dict(voice=v,source_before=before,source_after=after,
                volume_before=a['voices'][v,ch]['volume'],volume_after=b['voices'][v,ch]['volume'],
                amp_before=a['amplitudes'][v,ch],amp_after=b['amplitudes'][v,ch],
                source_changed_fields=[k for k in ('raw','env','noise','non','pitch','regpitch','delay','srcn','gain') if before[k]!=after[k]],
                nearby_observed_restarts=[dict(serial=e['serial'],packet=e['packet'],tick=e['tick'],
                    clocks_since_latch=after['tick']-e['tick'],keyon_write=e['keyon_write'],
                    first_pitch_matches=e['first_pitch_matches']) for e in restarts]))
        steady_noise = (all(a['sources'][3][k]==b['sources'][3][k] for k in ('env','non','flg','adsr','gain'))
            and a['voices'][3,ch]['volume']==b['voices'][3,ch]['volume']
            and a['mixes'][ch]['volume']==b['mixes'][ch]['volume'])
        events.append(dict(physical_seconds=event['physical']['seconds'],sample=sample,channel=ch,
            native_step=int(pcm[sample,ch])-int(pcm[sample-1,ch]),
            noise_transition=b['noise'],channels=channels,
            noise_transition_with_steady_controls=steady_noise,
            master_before=a['mixes'][ch],master_after=b['mixes'][ch],
            mixed_pitch_samples_within_128=[e for e in split if abs(e['sample']-sample)<=128]))
    # Independently corrupt each measured stage; the same reconstruction must
    # refuse, without weakening any tolerance to accommodate the real capture.
    sample = events[0]['sample']
    mutants = {}
    for name,kind,field in (('noise','N','after'),('envelope','S','env'),('volume','V','volume'),('mix','M','output')):
        rows = [r.copy() for r in groups[sample]]
        target = next(r for r in rows if r['kind']==kind and (kind!='S' or r['voice']==3))
        target[field] ^= 1
        try:
            validate_group(sample,rows,pcm[sample],register)
        except ValueError:
            mutants[name] = True
        else:
            mutants[name] = False
    if not all(mutants.values()):
        raise ValueError('Corrupted observation was not detected')
    out.mkdir(parents=True)
    paths = [Path(__file__),Path('tools/snes9x_voice_edge.inc'),Path('tools/capture_voice_edges.py'),
        Path('tools/audit_pulse_pitch.py'),Path('tools/review_native_transient_stems.py'),
        Path('tools/audit_pulse_onset.py'),Path('tools/audit_dsp_latency.py'),review/'report.json',
        observed/'voice-edge-observer.json',observed/'onset-observer.json',normal/'report.json',
        normal/'audio.wav',fixture/'manifest.json',trace,Path(noise_path)]
    result = dict(scope=__doc__,observer_neutral=True,raw_dac_identical=True,
        received_packets=onset['received_packets'],selected_samples=len(groups),noise_transitions=noise_changes,
        all_voice_dac_reconstructed=True,independent_noise_stem_exact=True,events=events,
        split_pitch_samples=split,negative_controls=mutants,pop_free_verified=False,release_ready=False,
        sources={str(p):sha(p) for p in paths})
    page = '<!doctype html><meta charset="utf-8"><title>DSP voice edges</title><style>body{max-width:1100px;margin:30px auto;background:#101821;color:#eee;font:17px system-ui}a{color:#9df}pre{white-space:pre-wrap}td,th{padding:10px;text-align:left}details{margin:20px 0}</style>'
    page += '<h1>Actual DSP channels at retained transient windows</h1><p>'+escape(__doc__)+'</p>'
    page += f'<p>{len(groups)} native stereo samples reconstructed from all eight source/voice stages, both master mixes and actual register-write timing. Independent noise-only PCM matches exactly. No production-ROM or hardware changes.</p>'
    page += '<p><a href="../'+review.name+'/">Native physical recordings, isolated-channel clips and waveform plots</a>. Windows and peaks are fixed by that earlier review. This does not phase-match physical audio or certify inaudibility.</p>'
    page += '<table><tr><th>Physical time</th><th>Noise controls steady</th><th>Pulse-2 restart context</th></tr>'
    for event in events:
        clocks = [r['clocks_since_latch'] for r in event['channels'][1]['nearby_observed_restarts']]
        page += f'<tr><td>{event["physical_seconds"]:.6f}s</td><td>{event["noise_transition_with_steady_controls"]}</td><td>{escape(str(clocks))} SPC clocks after observed KON latch</td></tr>'
    page += '</table><p>Steady-control noise transitions follow the DSP feedback recurrence exactly. A key-on boundary can still make a sharp pulse edge; a correctly transported/restarted note is not automatically faithful to NES audio or free of perceptible clicks.</p>'
    for event in events:
        page += f'<details><summary>Physical {event["physical_seconds"]:.6f}s → replay sample {event["sample"]}; step {event["native_step"]}</summary><pre>'+escape(json.dumps(event,indent=2))+'</pre></details>'
    page += '<p><a href="report.json">Complete source-bound results</a></p>'
    (out/'index.html').write_text(page)
    result['artifacts'] = {'index.html':sha(out/'index.html')}
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('selected_samples','noise_transitions','all_voice_dac_reconstructed',
        'independent_noise_stem_exact','split_pitch_samples','negative_controls')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('review','normal','observed','fixture','out'):
        p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
