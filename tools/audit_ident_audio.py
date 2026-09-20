"""Hash-bound PCM audit of a legato pitch-bend and short hardware echo."""
import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import wave

import numpy as np

GLIDE_CHECKPOINTS = (12, 28, 44, 60, 76, 92, 108, 124, 140, 159, 181, 202)


def curve_hz(path):
    payload = path.read_bytes()
    if len(payload) != 240 * 3:
        raise ValueError('Expected 240 three-byte S-DSP automation steps')
    return [int.from_bytes(payload[i:i + 2], 'little') * 1000 / 4096
            for i in range(0, len(payload), 3)]


def frequency(samples, sample_rate, expected):
    data = samples.astype(np.float64) - samples.mean()
    size = 1 << (2 * len(data) - 1).bit_length()
    spectrum = np.fft.rfft(data, n=size)
    autocorrelation = np.fft.irfft(spectrum * np.conj(spectrum), n=size)
    lower = int(sample_rate / (expected * 1.15))
    upper = int(sample_rate / (expected * 0.85))
    lag = lower + int(np.argmax(autocorrelation[lower:upper + 1]))
    return sample_rate / lag


def audit(capture):
    manifest_path = capture / 'capture.json'
    wav_path = capture / 'audio.wav'
    manifest = json.loads(manifest_path.read_text())
    rows = manifest['frames']
    envelope = curve_hz(capture.parent / 'splash-ident-curve.bin')
    with wave.open(str(wav_path)) as sound:
        rate = sound.getframerate()
        if sound.getnchannels() != 2 or sound.getsampwidth() != 2:
            raise ValueError('Expected original 16-bit, stereo libretro PCM')
        samples = np.frombuffer(sound.readframes(sound.getnframes()), '<i2').reshape(-1, 2)
    counts = [r['audio_sample_count'] for r in rows]
    offsets = np.cumsum([0] + counts)
    if offsets[-1] != len(samples):
        raise ValueError('WAV and per-frame callback lengths differ')
    measured = []
    for center in GLIDE_CHECKPOINTS:
        # Each window is seven successive VBlank-controlled pitches, not a
        # static eight-frame note. Middle-frame target approximates a smooth
        # glissando and catches stuck or stair-stepped APU pitch uploads.
        frames = [r['frame'] for r in rows if r['phase'] == 2
                  and center - 2 <= r['ident_note'] <= center + 4]
        if len(frames) != 7:
            raise ValueError(f'Missing glissando window at frame {center}: {frames}')
        start = offsets[frames[0] - 1]
        end = offsets[frames[-1]]
        data = samples[start:end, 0].astype(np.float64)
        expected = envelope[center]
        estimate = frequency(data, rate, expected)
        rms = float(np.sqrt(np.mean(data * data)))
        measured.append({'glide_frame': center, 'expected_hz': round(expected, 2),
                         'measured_hz': round(estimate, 2), 'error_percent':
                         round(abs(estimate / expected - 1) * 100, 3),
                         'rms_pcm': round(rms, 1), 'frames': frames})
    hold = [r for r in rows if r['phase'] == 2]
    end = offsets[hold[-1]['frame']]
    start = offsets[hold[0]['frame'] - 1]
    hold_pcm = samples[start:end].astype(np.int32)
    maximum_step = int(np.max(np.abs(np.diff(hold_pcm, axis=0))))
    rms = [item['rms_pcm'] for item in measured]
    gates = {
        'all_12_glide_windows_at_expected_pitch': all(item['error_percent'] < 5 for item in measured),
        'legato_chromatic_descent': len(set(envelope[:145])) >= 140
          and all(envelope[i] > envelope[i + 1] for i in range(144))
          and abs(envelope[0] - 311) < 0.2 and abs(envelope[144] - 110) < 0.2,
        'audible_pcm_each_note': min(rms) > 80,
        'low_bass_wobble_then_fade': any(envelope[k] < envelope[k+1] for k in range(150, 190))
          and int(np.max(np.abs(hold_pcm[-800:]))) < .25 * int(np.max(np.abs(hold_pcm))),
        'no_large_pcm_discontinuity': maximum_step < 5624,
        'balanced_stereo': int(np.max(np.abs(hold_pcm[:, 0] - hold_pcm[:, 1])))
          < 0.25 * int(np.max(np.abs(hold_pcm)))
          and abs(float(np.sqrt(np.mean(hold_pcm[:, 0].astype(float)**2))) /
                  float(np.sqrt(np.mean(hold_pcm[:, 1].astype(float)**2))) - 1) < 0.01,
            'wav_frame_count_matches_callbacks': int(offsets[-1]) == len(samples),
    }
    return {'passed': all(gates.values()), 'gates': gates, 'notes': measured,
            'audio_sample_rate': rate, 'max_consecutive_step_pcm': maximum_step,
            'curve_sha256': hashlib.sha256((capture.parent / 'splash-ident-curve.bin').read_bytes()).hexdigest(),
            'capture_sha256': hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            'wav_sha256': hashlib.sha256(wav_path.read_bytes()).hexdigest(),
            'rom_sha256': manifest['rom_sha256'],
            'scope': 'Emulator PCM frequency/volume/transient test; not subjective or hardware-audio certification'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    report = audit(args.capture)
    (args.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    source = html.escape(os.path.relpath(args.capture / 'audio.wav', args.out))
    table = ''.join('<tr>' + ''.join(f'<td>{html.escape(str(x))}</td>' for x in
                    (n['glide_frame'], n['expected_hz'], n['measured_hz'], n['error_percent'], n['rms_pcm']))
                    + '</tr>' for n in report['notes'])
    (args.out / 'index.html').write_text('''<!doctype html><meta charset="utf-8">
<title>Original sliding bass ident · SPC700 PCM audit</title>
<style>body{background:#10161c;color:#eee;font:16px system-ui;max-width:900px;margin:2em auto}
table{border-collapse:collapse}td,th{border:1px solid #46515a;padding:4px 9px}
tr:nth-child(even){background:#1a2930}a{color:#8eeaff}</style>
<h1>struktured labs bass ident · emulator PCM</h1>
<p>One sustained note bent once per frame through 18 chromatic semitone
landmarks from 311 Hz to 110 Hz, then a wobbling fade with a DSP echo.
Twelve measured windows use autocorrelation on real stereo emulator PCM,
independent of CPU pitch writes. This does not certify the subjective timbre.</p>
<audio controls src="''' + source + '''"></audio>
<p><a href="report.json">Raw hashes, all gates and note observations</a></p>
<table><tr><th>Glide frame</th><th>Target Hz</th><th>Captured Hz</th><th>Error %</th><th>RMS PCM</th></tr>'''
       + table + '</table>')
    print(json.dumps(report['gates'], indent=2))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
