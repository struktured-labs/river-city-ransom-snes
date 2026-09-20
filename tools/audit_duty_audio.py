"""Pixel-independent waveform audit of the isolated duty-key-on experiment."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import wave

import numpy as np


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def near_zero_run(samples, threshold=8):
    quiet = np.abs(np.asarray(samples, dtype=float)) < threshold
    if quiet.ndim != 1:
        raise ValueError('Need one channel')
    edges = np.flatnonzero(np.diff(np.r_[False, quiet, False]))
    return int(max(edges[1::2]-edges[::2], default=0))


def load(root, expected_profile):
    report = json.loads((root/'report.json').read_text())
    if report['profile'] != expected_profile or not report['passed']:
        raise ValueError('Need a passing duty-only tone-presence capture')
    for file, field in [('audio.wav', 'wav_sha256'), ('timeline.json', 'timeline_sha256')]:
        if sha(root/file) != report[field]:
            raise ValueError('Capture artifact hash mismatch')
    with wave.open(str(root/'audio.wav')) as wav:
        if wav.getnchannels() != 2 or wav.getsampwidth() != 2:
            raise ValueError('Need stereo PCM16')
        rate = wav.getframerate()
        pcm = np.frombuffer(wav.readframes(wav.getnframes()), '<i2').reshape(-1, 2)
    timeline = json.loads((root/'timeline.json').read_text())
    if timeline[-1]['end_sample'] != len(pcm):
        raise ValueError('Timeline does not cover PCM')
    return report, timeline, rate, pcm


def audit(current, suppressed, out):
    sources = [load(current, 'duty-only'), load(suppressed, 'duty-only-keyon-suppressed')]
    if sources[0][2] != sources[1][2]:
        raise ValueError('Sample rates differ')
    events, cards = [], []
    for frame in (32, 64, 96, 192, 224, 256, 288, 320):
        measurements, plots = [], []
        for label, (_, timeline, rate, pcm) in zip(('current', 'suppressed'), sources):
            matches = [r for r in timeline if r['driver_frame'] == frame]
            if len(matches) != 1:
                raise ValueError('Missing or duplicate duty event')
            row = matches[0]
            if row['channel_enable'] != 1 or row['periodic_retriggers']:
                raise ValueError('Duty event is muted or includes periodic note resets')
            samples = pcm[row['start_sample']:row['start_sample']+600]
            if len(samples) != 600:
                raise ValueError('Truncated event PCM')
            runs = [near_zero_run(samples[:, channel]) for channel in range(2)]
            measurements.append(dict(variant=label, start_sample=row['start_sample'],
                                     sample_count=600, pulse_control=row['pulse_control'],
                                     longest_near_zero_samples=runs,
                                     longest_near_zero_ms=[n*1000/rate for n in runs]))
            points = ' '.join(f'{i*2},{60-float(s)/50:.2f}' for i,s in enumerate(samples[:, 0]))
            plots.append(f'<p>{label}: near-zero run {runs} samples [L,R]</p>'
                         f'<svg viewBox="0 0 1200 120"><polyline fill="none" stroke="cyan" stroke-width="1" points="{points}"/></svg>')
        events.append(dict(driver_frame=frame, measurements=measurements))
        cards.append(f'<h2>Duty update at driver frame {frame}</h2>'+''.join(plots))
    out.mkdir(parents=True, exist_ok=False)
    for label, root in [('current', current), ('suppressed', suppressed)]:
        shutil.copyfile(root/'audio.wav', out/f'{label}.wav')
    result = dict(schema='rcr-duty-waveform-audit-v1',
                  scope='600 samples after each frame callback boundary; no waveform phase alignment, no NES equivalence or game-click verdict',
                  near_zero_threshold=8, sample_rate=sources[0][2],
                  report_sha256=[sha(root/'report.json') for root in (current, suppressed)], events=events)
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Duty-change audio audit</title>'
        '<style>body{background:#111;color:#eee;font:16px sans-serif;max-width:1200px;margin:auto}svg{width:100%;background:#222}</style>'
        '<h1>Duty-change key-on experiment</h1><p>Current versus experimental suppression. '
        'Left waveforms shown; both channels measured. Not a NES equivalence or gameplay verdict.</p>'
        '<h2>Current</h2><audio controls src="current.wav"></audio>'
        '<h2>Experimental</h2><audio controls src="suppressed.wav"></audio>'
        '<p><a href="report.json">Measurement windows and source hashes</a></p>'+''.join(cards))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('current', 'suppressed', 'out'):
        parser.add_argument('--'+option, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.current, args.suppressed, args.out), indent=2))
