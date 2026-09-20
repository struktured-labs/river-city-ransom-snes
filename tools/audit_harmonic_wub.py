"""Native before/after audition; pitch, harmonic motion and game handoff gates."""
import argparse
import json
from pathlib import Path
import shutil

import numpy as np
from scipy.io import wavfile

from tools.audit_sub_wub import measure
from tools.benchmark_report import sha
from tools.build_harmonic_wub_trial import patch
from tools.check_branding_splash import evaluate


def harmonic_motion(pcm, rate, rows):
    offsets = np.cumsum([0]+[r['audio_sample_count'] for r in rows])
    hold = [r for r in rows if r['phase'] == 2]
    results = []
    for note in (144,174,204):
        ratios = []
        for first,last in ((note,note+8),(note+13,note+21)):
            a,b = offsets[hold[first]['frame']-1],offsets[hold[last]['frame']]
            samples = pcm[a:b,0].astype(float)
            samples -= samples.mean()
            power = np.abs(np.fft.rfft(samples*np.hanning(len(samples))))**2
            hz = np.fft.rfftfreq(len(samples),1/rate)
            bass = power[(hz>=35)&(hz<=85)].sum()
            if bass <= 0:
                raise ValueError('No bass in harmonic analysis window')
            ratios.append(float(power[(hz>=95)&(hz<=1500)].sum()/bass))
        results.append(dict(note=note, open_harmonic_to_bass=ratios[0],
            closed_harmonic_to_bass=ratios[1], contrast=ratios[0]/max(ratios[1],1e-15)))
    return results


def comparison_gates(new, old):
    if len(new) != 3 or [x['note'] for x in new] != [x['note'] for x in old]:
        raise ValueError('Expected matching three-pulse windows')
    return dict(
        stronger_open_harmonics=all(a['open_harmonic_to_bass']>b['open_harmonic_to_bass']*1.5
                                   for a,b in zip(new,old)),
        deeper_harmonic_motion=all(a['contrast']>b['contrast']*1.5 for a,b in zip(new,old)))


def audit(parent, candidate, baseline, core, out):
    if out.exists():
        raise ValueError('Fresh report path required')
    captures = (candidate/'capture', baseline)
    receipts = [json.loads((p/'capture.json').read_text()) for p in captures]
    sounds = [wavfile.read(p/'audio.wav') for p in captures]
    source_files = [Path(__file__), Path('tools/build_harmonic_wub_trial.py'),
        Path('tools/build_ident_spc.py'), Path('tools/build_sub_wub_trial.py'),
        Path('tools/build_inline_pitch_trial.py'), Path('tools/audit_sub_wub.py'),
        Path('tools/check_branding_splash.py'),Path('tools/capture_branding_splash.py'),
        Path('tests/test_harmonic_wub.py'), core]
    for folder, receipt in zip((candidate,parent),receipts):
        manifest = json.loads((folder/'manifest.json').read_text())
        if (receipt['rom_sha256'] != sha(folder/'native-cpu.sfc') or
                receipt['rom_sha256'] != manifest['rom_sha256'] or
                receipt['core_sha256'] != sha(core) or
                receipt['harness_sha256'] != sha(Path('tools/capture_branding_splash.py')) or
                receipt['fps'] != receipts[0]['fps']):
            raise ValueError('Unbound or mismatched capture')
        source_files += [folder/n for n in ('native-cpu.sfc','manifest.json',
            'splash-ident-spc.bin','splash-ident-curve.bin')]
    if sounds[0][0] != sounds[1][0] or sounds[0][1].shape != sounds[1][1].shape:
        raise ValueError('Native rates or lengths differ')
    rows, oldrows = [r['frames'] for r in receipts]
    rate = sounds[0][0]
    result, control = [measure(pcm,rr,receipt['frames'])
                       for (rr,pcm),receipt in zip(sounds,receipts)]
    motion = [harmonic_motion(pcm,rr,receipt['frames'])
              for (rr,pcm),receipt in zip(sounds,receipts)]
    counts = [np.cumsum([0]+[r['audio_sample_count'] for r in rs]) for rs in (rows,oldrows)]
    handoffs = [next(r['frame'] for r in rs if r['phase']==3) for rs in (rows,oldrows)]
    game = [pcm[off[f-1]:] for (_,pcm),off,f in zip(sounds,counts,handoffs)]
    excluded = {'audio_peak','audio_sample_count'}
    visual_exact = len(rows)==len(oldrows)==950 and all(
        {k:v for k,v in a.items() if k not in excluded} ==
        {k:v for k,v in b.items() if k not in excluded} for a,b in zip(rows,oldrows))
    sample_differences = [dict(frame=a['frame'], before=b['audio_sample_count'],
        after=a['audio_sample_count']) for a,b in zip(rows,oldrows)
        if a['audio_sample_count']!=b['audio_sample_count']]
    tail = next(r['frame'] for r in rows if r['phase']==2 and r['ident_note']==144)
    pre_end = int(counts[0][tail-1])
    delta = sounds[0][1][:pre_end].astype(int)-sounds[1][1][:pre_end].astype(int)
    expected, offset = patch((parent/'native-cpu.sfc').read_bytes())
    visuals = evaluate(candidate)
    gates = dict(**result['gates'], **comparison_gates(*motion),
        original_control_rejected=not all(comparison_gates(motion[1],motion[1]).values()),
        only_ident_payload_and_checksum=expected==(candidate/'native-cpu.sfc').read_bytes(),
        unchanged_pitch_and_volume_table=(candidate/'splash-ident-curve.bin').read_bytes()==
            (parent/'splash-ident-curve.bin').read_bytes(),
        all950_visual_ram_timing_rows_exact=visual_exact,
        original_game_audio_exact=np.array_equal(*game),
        splash_visual_and_boot=all(visuals['gates'].values()))
    out.mkdir(parents=True)
    clips = []
    for label,folder,(rr,pcm),receipt,off in zip(('after','before'),captures,sounds,receipts,counts):
        hold = [r['frame'] for r in receipt['frames'] if r['phase']==2]
        first,last = int(off[hold[0]-1]),int(off[hold[-1]])
        wavfile.write(out/(label+'.wav'),rr,pcm[first:last])
        clips.append(dict(file=label+'.wav',source=str(folder/'audio.wav'),first=first,last=last,rate=rr))
        source_files += [folder/'audio.wav',folder/'capture.json']
    pictures = []
    for note in (144,174,204):
        row = next(r for r in rows if r['phase']==2 and r['ident_note']==note)
        source = candidate/'capture'/row['image']
        name = f'pulse-{note}.png'
        shutil.copy2(source,out/name); source_files.append(source); pictures.append(name)
    levels = result['rms']; maximum = max(levels)
    points = ' '.join(f'{20+i*960/239:.2f},{220-v*190/maximum:.2f}' for i,v in enumerate(levels))
    (out/'envelope.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 250">'
        '<rect width="1000" height="250" fill="#101820"/><polyline fill="none" stroke="#63d7ff" points="'+points+'"/>'
        '<text x="20" y="245" fill="white">Four seconds: slide, three slow 55 Hz pulses, echo decay</text></svg>')
    report = dict(passed=all(gates.values()),gates=gates,candidate=result,control=control,
        harmonic_motion=dict(after=motion[0],before=motion[1]),
        spc_rom_offset=offset, callback_sample_count_changes=sample_differences,
        pre_tail_changed_channel_samples=int(np.count_nonzero(delta)),
        pre_tail_maximum_delta_pcm=int(np.abs(delta).max()),
        pre_tail_comparison_samples=pre_end,
        physical_verified=False, subjective_timbre_approved=False,release_ready=False,
        scope='Native Snes9x PCM; no gain, resampling, phase fitting or filtering of audition audio. '
            'Band-power analysis is not a subjective dubstep or physical-hardware certification. '
            'Extra SPC instructions can shift individual volume writes and callback sample boundaries.',
        clips=clips,sources={str(p):sha(p) for p in source_files})
    (out/'index.html').write_text('''<!doctype html><meta charset="utf-8"><title>Harmonic WUB audition</title>
<style>body{background:#101820;color:#eee;font:18px system-ui;max-width:1000px;margin:2em auto}
a{color:cyan}audio{width:100%}.logo{width:30%;image-rendering:pixelated}img.graph{width:100%}</style>
<h1>struktured labs — deeper WUB motion</h1>
<p>Fixed 55 Hz bass, three slow pulses, then stop. The gritty octave now opens and closes more deeply with each pulse.
Original slide automation and echo remain; no pitch wobble added to the ending.</p>
<h2>New audition</h2><audio controls src="after.wav"></audio>
<h2>Current Rival build</h2><audio controls src="before.wav"></audio>
<p>Native, unnormalized emulator recordings. New audition is NOT deployed or hardware-qualified.</p>
<img class="graph" src="envelope.svg">'''+''.join('<img class="logo" src="'+name+'">' for name in pictures)+
        '<p>Checks: '+('PASS' if report['passed'] else 'FAIL')+
        '. Visual/RAM/timing observations and post-handoff game audio match. '
        'SPC instruction timing produces small pre-tail PCM differences and callback-boundary changes; '
        'these are retained in the report, not called bit-identical audio.</p>'
        '<p><a href="report.json">Measurements, limitations and source hashes</a></p>')
    report['artifacts'] = {p.name:sha(p) for p in out.iterdir() if p.is_file()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'],gates=gates,harmonic_motion=report['harmonic_motion'])))
    return report['passed']


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','candidate','baseline','core','out'):
        p.add_argument('--'+name,type=Path,required=True)
    raise SystemExit(0 if audit(**vars(p.parse_args())) else 1)
