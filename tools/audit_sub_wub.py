"""Native, unnormalized splash audition and isolated-change/handoff checks."""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from tools.benchmark_report import sha
from tools.build_sub_wub_trial import patch
from tools.check_branding_splash import evaluate


def fundamental(samples, rate):
    # Broad-band strongest component, not autocorrelation constrained around
    # the expected note (which can accept an octave-up note at double lag).
    data=samples.astype(float); data-=data.mean()
    n=1 << (len(data)*4-1).bit_length()
    spectrum=np.abs(np.fft.rfft(data*np.hanning(len(data)),n=n))
    lo,hi=int(35*n/rate),int(350*n/rate)
    k=lo+int(np.argmax(spectrum[lo:hi]))
    a,b,c=np.log(np.maximum(spectrum[k-1:k+2],1e-12))
    delta=.5*(a-c)/(a-2*b+c)
    return float((k+delta)*rate/n)


def measure(pcm, rate, rows):
    offsets = np.cumsum([0]+[r['audio_sample_count'] for r in rows])
    hold = [r for r in rows if r['phase'] == 2]
    if (pcm.dtype != np.int16 or pcm.shape[1:] != (2,) or offsets[-1] != len(pcm)
            or [r['ident_note'] for r in hold] != list(range(240))):
        raise ValueError('Incomplete native stereo capture / ident sequence')
    rms = np.array([np.sqrt(np.mean(pcm[offsets[r['frame']-1]:offsets[r['frame']]].astype(float)**2)) for r in hold])
    # Fixed 5-frame energy averaging: >4 cycles at55 Hz; not audio processing.
    envelope = np.sqrt(np.convolve(rms*rms, np.ones(5)/5, mode='same'))
    pulses = []
    for n in (144,174,204):
        peak = max(range(n,n+10), key=lambda i:envelope[i])
        trough = min(range(n+13,n+22), key=lambda i:envelope[i])
        a,b = hold[n]['frame'], hold[n+11]['frame']
        pulses.append(dict(peak_note=peak, trough_note=trough,
            peak_rms=float(envelope[peak]), trough_ratio=float(envelope[trough]/envelope[peak]),
            hz=fundamental(pcm[offsets[a-1]:offsets[b],0],rate)))
    gates = dict(three_deep_pulses=all(p['peak_rms']>500 and p['trough_ratio']<.35 for p in pulses),
        fixed_55hz_note=all(abs(p['hz']/55-1)<.05 for p in pulses),
        half_second_spacing=all(28<=b['peak_note']-a['peak_note']<=32 for a,b in zip(pulses,pulses[1:])),
        decayed_before_stop=bool(rms[-1]<rms.max()*.02),
        no_clipping=int(np.abs(pcm.astype(np.int32)).max())<32767)
    return dict(gates=gates, pulses=pulses, rms=rms.tolist())


def audit(parent, candidate, baseline, core, out):
    if out.exists():
        raise ValueError('Fresh report path required')
    captures = (candidate/'capture', baseline)
    receipts = [json.loads((p/'capture.json').read_text()) for p in captures]
    sounds = [wavfile.read(p/'audio.wav') for p in captures]
    for folder, receipt in zip((candidate,parent),receipts):
        manifest = json.loads((folder/'manifest.json').read_text())
        if (receipt['rom_sha256'] != sha(folder/'native-cpu.sfc') or
                receipt['rom_sha256'] != manifest['rom_sha256'] or
                receipt['core_sha256'] != sha(core) or
                receipt['harness_sha256'] != sha(Path('tools/capture_branding_splash.py'))):
            raise ValueError('Unbound capture')
    if sounds[0][0] != sounds[1][0] or sounds[0][1].shape != sounds[1][1].shape:
        raise ValueError('Native rates/lengths differ')
    rate = sounds[0][0]
    rows, oldrows = [r['frames'] for r in receipts]
    result = measure(sounds[0][1],rate,rows)
    control = measure(sounds[1][1],rate,oldrows)
    allowed = {'audio_peak'}
    # Audio sample counts, every image hash and all RAM/timing observations
    # remain exact; only the audio waveform's peak field may change.
    same = len(rows)==len(oldrows)==950 and all(
        {k:v for k,v in a.items() if k not in allowed} ==
        {k:v for k,v in b.items() if k not in allowed} for a,b in zip(rows,oldrows))
    offsets = np.cumsum([0]+[r['audio_sample_count'] for r in rows])
    handoff = next(r['frame'] for r in rows if r['phase']==3)
    expected, offset = patch((parent/'native-cpu.sfc').read_bytes())
    visual = evaluate(candidate)
    gates = dict(**result['gates'], only_ident_table_and_checksum=expected==(candidate/'native-cpu.sfc').read_bytes(),
        all950_non_audio_rows_exact=same,
        original_game_audio_exact=np.array_equal(sounds[0][1][offsets[handoff-1]:],sounds[1][1][offsets[handoff-1]:]),
        splash_visual_and_boot=all(visual['gates'].values()),
        old_octave_rejected=not control['gates']['fixed_55hz_note'])
    sources = [Path(__file__),Path('tools/build_sub_wub_trial.py'),Path('tools/build_wub_tail_trial.py'),
        Path('tools/build_inline_pitch_trial.py'),Path('tools/build_ident_spc.py'),
        Path('tools/audit_ident_audio.py'),Path('tools/check_branding_splash.py'),
        Path('tools/capture_branding_splash.py'),core]
    sources += [folder/name for folder in (parent,candidate) for name in ('native-cpu.sfc','manifest.json','splash-ident-curve.bin')]
    sources += [folder/name for folder in captures for name in ('capture.json','audio.wav')]
    report = dict(passed=all(gates.values()), gates=gates, candidate=result, control=control,
        physical_verified=False, subjective_timbre_approved=False, release_ready=False,
        table_offset=offset, sources={str(p):sha(p) for p in sources})
    out.mkdir(parents=True)
    # Exact sample cuts: no normalization, filtering, resampling or crossfade.
    for label, (sample_rate,pcm), receipt in zip(('after','before'),sounds,receipts):
        rs=receipt['frames']; off=np.cumsum([0]+[r['audio_sample_count'] for r in rs])
        hold=[r['frame'] for r in rs if r['phase']==2]
        wavfile.write(out/(label+'.wav'),sample_rate,pcm[off[hold[0]-1]:off[hold[-1]]])
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'index.html').write_text('''<!doctype html><meta charset="utf-8"><title>Slower sub-bass WUB audition</title>
<style>body{background:#101820;color:#eee;font:18px system-ui;max-width:850px;margin:3em auto}a{color:cyan}audio{width:100%}</style>
<h1>struktured labs — sub-bass ending</h1><p>Smooth slide to a fixed55 Hz note, then three deep half-second pulses and a stop.
Existing echo drains before the game starts. Native emulator PCM, no loudness normalization.</p>
<h2>New:55 Hz landing</h2><audio controls src="after.wav"></audio>
<h2>Previous:110 Hz landing</h2><audio controls src="before.wav"></audio>
<p>Emulator checks: '''+('PASS' if report['passed'] else 'FAIL')+'''. This is an audition, not hardware validation or subjective approval.
Game audio after handoff and all950 non-audio rows are checked for exact equality.</p><a href="report.json">All gates, measurements and source hashes</a>''')
    print(json.dumps(dict(passed=report['passed'],gates=gates,pulses=result['pulses'])))
    return report['passed']


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','candidate','baseline','core','out'):
        p.add_argument('--'+name,type=Path,required=True)
    raise SystemExit(0 if audit(**vars(p.parse_args())) else 1)
