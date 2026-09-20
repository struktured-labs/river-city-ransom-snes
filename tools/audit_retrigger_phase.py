"""Fixed-window pulse phase repeatability; no waveform alignment or game verdict."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import wave
import numpy as np


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(sources, out):
    out.mkdir(parents=True, exist_ok=False)
    results, cards = {}, []
    selected_pulse2 = None
    for name, root in sources.items():
        report = json.loads((root/'report.json').read_text())
        expected_profile = 'periodic-retrigger-control' if name == 'nes_control' else 'periodic-retrigger'
        if not report.get('passed') or report.get('profile') != expected_profile:
            raise ValueError('Wrong or failed source profile')
        pulse2 = bool(report.get('pulse2', report.get('pulse2_experiment', False)))
        if selected_pulse2 is not None and pulse2 != selected_pulse2:
            raise ValueError('Cannot compare different pulse voices')
        selected_pulse2 = pulse2
        if name in ('legacy_spc', 'reset_spc') and bool(report.get('reset_notes_experiment')) != (name == 'reset_spc'):
            raise ValueError('SPC reset/control roles do not match')
        for filename, field in [('audio.wav', 'wav_sha256'), ('timeline.json', 'timeline_sha256')]:
            if sha(root/filename) != report[field]:
                raise ValueError('Source hash mismatch')
        timeline = json.loads((root/'timeline.json').read_text())
        with wave.open(str(root/'audio.wav')) as wav:
            if wav.getnchannels() != 2 or wav.getsampwidth() != 2:
                raise ValueError('Need stereo PCM16')
            rate = wav.getframerate()
            pcm = np.frombuffer(wav.readframes(wav.getnframes()), '<i2').reshape(-1, 2)
        if timeline[-1]['end_sample'] != len(pcm):
            raise ValueError('Incomplete waveform timeline')
        phases, events = [], []
        cards.append(f'<h2>{name}</h2><audio controls src="{name}.wav"></audio>')
        for frame in (32, 64, 96, 192, 224):
            rows = [r for r in timeline if r['driver_frame'] == frame]
            if len(rows) != 1 or rows[0]['phase'] not in (0, 2):
                raise ValueError('Missing, duplicate or wrong-phase event')
            start = rows[0]['end_sample'] + round(rate*.002)
            stop = start + round(rate*.008)
            samples = pcm[start:stop].astype(float)
            if len(samples) != stop-start:
                raise ValueError('Truncated event window')
            samples -= samples.mean(axis=0)
            frequency = 1789773/(16*254)
            z = np.sum(samples*np.exp(-2j*np.pi*frequency*np.arange(len(samples))/rate)[:, None], axis=0)
            if min(abs(z)) < 1:
                raise ValueError('No usable fundamental component')
            phase = z/abs(z)
            phases.append(phase)
            events.append(dict(frame=frame, start_sample=start, end_sample=stop,
                               phase_radians=np.angle(phase).tolist()))
            points = ' '.join(f'{i*800/(len(samples)-1):.2f},{60-s/80:.2f}'
                              for i, s in enumerate(samples[:, 0]))
            cards.append(f'<p>Frame {frame}; left channel, DC removed for plot only.</p>'
                         f'<svg viewBox="0 0 800 120"><polyline fill="none" stroke="cyan" points="{points}"/></svg>')
        coherence = abs(np.mean(phases, axis=0)).tolist()
        results[name] = dict(coherence=coherence, events=events, sample_rate=rate,
                             source_report_sha256=sha(root/'report.json'), wav_sha256=sha(root/'audio.wav'))
        shutil.copyfile(root/'audio.wav', out/f'{name}.wav')
    passed = (all(min(results[k]['coherence']) > .95 for k in ('nes', 'reset_spc'))
              and all(max(results[k]['coherence']) < .5 for k in ('nes_control', 'legacy_spc')))
    result = dict(passed=passed, release_ready=False, variants=results,
                  pulse2=selected_pulse2,
                  scope='Five same-pitch reset events, both channels; phase repeatability, NOT exact inter-system phase, waveform, duty/pitch transitions or gameplay fidelity',
                  window='2..10 ms after event callback end; fixed, no alignment or phase fitting across events',
                  positive_min_coherence=.95, control_max_coherence=.5)
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Pulse reset audit</title>'
        '<style>body{background:#111;color:#eee;font:16px sans-serif;max-width:900px;margin:auto}svg{width:100%}</style>'
        '<h1>Pulse phase repeatability</h1><p>Fixed windows, no waveform alignment. '
        'Audio is unmodified. Plots remove DC only; both channels are measured. '
        'Not exact NES/SPC fidelity or a gameplay verdict.</p><a href="report.json">Measurements and hashes</a>'
        + ''.join(cards))
    print(json.dumps(dict(passed=passed, coherence={k:v['coherence'] for k,v in results.items()}), indent=2))
    return passed


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('nes', 'nes_control', 'legacy_spc', 'reset_spc', 'out'):
        parser.add_argument('--'+name.replace('_','-'), type=Path, required=True)
    args = vars(parser.parse_args())
    out = args.pop('out')
    raise SystemExit(0 if audit(args, out) else 1)
