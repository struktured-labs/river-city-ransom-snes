"""Qualify a nearby read-only OBS audio extraction, not game sound fidelity."""
import argparse
import html
import json
from pathlib import Path
import wave

import numpy as np

from tools.benchmark_report import sha


def metrics(samples, rate):
    if samples.ndim != 2 or samples.shape[1] != 2 or rate != 48000 or len(samples) < rate:
        raise ValueError('Need at least one second of stereo 48kHz PCM')
    data = samples.astype(np.float64)
    centered = data-data.mean(axis=0)
    return dict(seconds=len(data)/rate, sample_rate=rate, channels=2,
        rms=float(np.sqrt(np.mean(data*data))),
        ac_rms_by_channel=np.sqrt(np.mean(centered*centered, axis=0)).tolist(),
        peak=int(np.max(np.abs(data))), nonzero_samples=int(np.count_nonzero(data)),
        clipped_samples=int(np.count_nonzero(np.abs(data) >= 32767)),
        per_second_rms=[float(np.sqrt(np.mean(data[i:i+rate]**2)))
                        for i in range(0, len(data), rate)])


def nearby(provenance, offset, duration):
    if offset < 0 or duration <= 0:
        raise ValueError('Invalid recording interval')
    gap = provenance['recording_duration_ms']/1000-offset-duration
    if not 0 <= gap <= 2:
        raise ValueError('Settings observation is not within two seconds after audio interval')
    return bool(provenance['recording_active'] and provenance['scene'] == 'river city ransom'
        and not provenance['blackmagic']['mute'] and provenance['blackmagic']['volume'] > 0
        and provenance['desktop_muted'] and provenance['microphone_muted'])


def audit(audio, provenance, screenshot, recording, offset, seconds, out):
    with wave.open(str(audio)) as source:
        if source.getsampwidth() != 2 or source.getnchannels() != 2:
            raise ValueError('Need signed16 stereo extraction')
        data = np.frombuffer(source.readframes(source.getnframes()), '<i2').reshape(-1, 2)
        result = metrics(data, source.getframerate())
    if result['seconds'] != seconds:
        raise ValueError('Truncated extraction')
    state = json.loads(provenance.read_text())
    isolated = nearby(state, offset, seconds)
    if not screenshot.is_file():
        raise ValueError('Missing nearby program screenshot')
    result.update(recording_path=recording, extraction_offset=offset,
        blackmagic_only_nearby_settings=isolated,
        recording_audio_path_nonsilent=isolated and all(x > 1 for x in result['ac_rms_by_channel']),
        hardware_game_fidelity_verified=False, release_ready=False,
        sources={str(p): sha(p) for p in (audio, provenance, screenshot, Path(__file__))},
        scope='Read-only extraction from an ongoing OBS recording. Nearby settings/screenshot '
              'do not prove immutable historical routing or exact active cartridge identity. '
              'Non-silent AC audio establishes a usable sampled capture path, not NES tempo, '
              'absence of pops, subjective timbre, current experimental ROM or gameplay quality. '
              'The live growing MKV is identified by path/offset, not a stable whole-file hash.')
    out.mkdir(parents=True, exist_ok=False)
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>OBS audio capture path</title>'
        '<style>body{background:#101821;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}'
        'a{color:#9df}img{max-width:100%}audio{width:100%}</style>'
        '<h1>Current OBS recording contains menu audio</h1><p>'+html.escape(result['scope'])+'</p>'
        f'<audio controls src="../{html.escape(audio.name)}"></audio>'
        f'<p>{result["seconds"]} seconds; RMS {result["rms"]:.2f}, peak {result["peak"]}, '
        f'{result["nonzero_samples"]} nonzero samples. Nearby settings isolate Blackmagic: {isolated}.</p>'
        f'<img src="../{html.escape(screenshot.name)}">'
        '<p><a href="report.json">Provenance, limitations and hashes</a></p>')
    print(json.dumps({k:result[k] for k in ('recording_audio_path_nonsilent','seconds','rms','peak')}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('audio', 'provenance', 'screenshot', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--recording', required=True)
    p.add_argument('--offset', type=float, required=True)
    p.add_argument('--seconds', type=float, required=True)
    audit(**vars(p.parse_args()))
