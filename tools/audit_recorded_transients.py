"""Locate reviewable PCM discontinuities and silence in a physical recording.

Ranks measured changes; does not classify NES attacks/noise as defects or infer
inaudibility from low absolute amplitude. No normalization or tempo adjustment.
"""
import argparse
import html
import json
from pathlib import Path
import wave

import numpy as np

from tools.audit_hardware_pause_pair import read_pcm
from tools.audit_recording_audio_path import metrics
from tools.benchmark_report import sha


def zero_runs(pcm):
    silent = np.all(pcm == 0, axis=1)
    edges = np.diff(np.r_[False, silent, False].astype(np.int8))
    return [(int(a), int(b)) for a, b in zip(np.flatnonzero(edges == 1),
                                            np.flatnonzero(edges == -1))]


def measure(pcm, rate=48000, count=8):
    if pcm.dtype != np.dtype('<i2') or type(count) is not int or count < 1:
        raise ValueError('Need signed16 PCM and a positive review count')
    result = metrics(pcm, rate)
    steps = np.abs(np.diff(pcm.astype(np.int32), axis=0))
    largest = steps.max(axis=1)
    remaining = largest.copy()
    events = []
    # Select strongest remaining step, then exclude half a second on each side.
    # A strict separation rule prevents one attack from occupying all eight slots.
    for _ in range(count):
        at = int(np.argmax(remaining))
        if remaining[at] < 0:
            break
        sample = at + 1
        channel = int(np.argmax(steps[at]))
        events.append(dict(sample=sample, seconds=sample/rate, channel=channel,
            step=int(steps[at, channel]), before=int(pcm[sample-1, channel]),
            after=int(pcm[sample, channel]),
            clip_first_sample=max(0, sample-rate//2),
            clip_last_sample=min(len(pcm), sample+rate//2)))
        remaining[max(0, at-rate//2):min(len(remaining), at+rate//2+1)] = -1
    runs = zero_runs(pcm)
    result.update(max_adjacent_step=int(largest.max()), strongest_separated_events=events,
        longest_exact_zero_frames=max((b-a for a, b in runs), default=0),
        exact_zero_runs_at_least_10ms=[dict(first_sample=a, last_sample=b,
            seconds=(b-a)/rate) for a, b in runs if b-a >= rate/100],
        pop_free_verified=False, tempo_verified=False, release_ready=False)
    return result


def sensitivity(pcm, rate):
    at = len(pcm)//2
    click = pcm.copy()
    click[at, 0], click[at+1, 0] = -32768, 32767
    click_result = measure(click, rate, 1)
    muted = pcm.copy()
    muted[at:at+rate//20] = 0
    mute_result = measure(muted, rate, 1)
    return dict(full_scale_step_detected=click_result['max_adjacent_step'] == 65535,
        clipping_detected=click_result['clipped_samples'] >= 2,
        inserted_50ms_silence_detected=any(run['first_sample'] <= at and
            run['last_sample'] >= at+rate//20
            for run in mute_result['exact_zero_runs_at_least_10ms']))


def waveform_svg(pcm):
    # Display min/max in 500 bins at the same full-scale range for every clip.
    # Generated measurement graphic, not altered game imagery.
    mono = pcm.astype(np.int32)
    lines = []
    for x, segment in enumerate(np.array_split(mono, min(500, len(mono)))):
        top = 50-float(segment.max())/32768*48
        bottom = 50-float(segment.min())/32768*48
        lines.append(f'<path d="M{x} {top:.3f}V{bottom:.3f}"/>')
    return ('<svg viewBox="0 0 500 100" role="img" aria-label="PCM min/max, full scale">'
            '<path d="M0 50H500" stroke="#567"/><g stroke="#6df">'
            + ''.join(lines) + '</g></svg>')


def audit(audio, offset, out):
    if not np.isfinite(offset) or offset < 0:
        raise ValueError('Need finite nonnegative recording offset')
    pcm = read_pcm(audio)
    result = measure(pcm)
    result.update(recording_offset_seconds=offset, audio_sha256=sha(audio),
        sensitivity_controls=sensitivity(pcm, 48000),
        scope='Decoded physical recording, not emulator PCM. Largest separated sample '
              'steps are review candidates, not identified pops: normal pulse/noise '
              'attacks can produce large steps. Exact-zero spans do not identify their '
              'cause. OBS gain, codec and resampling affect these measurements. '
              'No frame-exact input/event correlation, tempo or pop-free certification.',
        implementation_sha256={str(p): sha(p) for p in (Path(__file__),
            Path('tools/audit_hardware_pause_pair.py'), Path('tools/audit_recording_audio_path.py'))})
    out.mkdir(parents=True, exist_ok=False)
    cards = []
    artifacts = {}

    def clip(name, first, last):
        data = pcm[first:last]
        with wave.open(str(out/name), 'wb') as target:
            target.setparams((2, 2, 48000, 0, 'NONE', 'not compressed'))
            target.writeframes(data.tobytes())
        artifacts[name] = sha(out/name)
        return waveform_svg(data) + f'<audio controls preload="none" src="{name}"></audio>'

    for number, event in enumerate(result['strongest_separated_events'], 1):
        name = f'event-{number:02d}.wav'
        event.update(clip=name, recording_seconds=offset+event['seconds'])
        cards.append(f'<section><h3>#{number}: recording {event["recording_seconds"]:.6f}s</h3>'
            f'<p>Sample {event["sample"]}, channel {event["channel"]}; '
            f'{event["before"]} → {event["after"]}, step {event["step"]}.</p>'
            + clip(name,event['clip_first_sample'],event['clip_last_sample'])+'</section>')
    quiet_cards = []
    longest = sorted(result['exact_zero_runs_at_least_10ms'],
                     key=lambda run: -run['seconds'])[:8]
    for number, run in enumerate(longest, 1):
        name = f'silence-{number:02d}.wav'
        first = max(0, run['first_sample']-24000)
        last = min(len(pcm), run['last_sample']+24000)
        run.update(clip=name, clip_first_sample=first, clip_last_sample=last,
                   recording_seconds=offset+run['first_sample']/48000)
        quiet_cards.append(f'<section><h3>{run["seconds"]*1000:.3f}ms exact silence</h3>'
            f'<p>Recording {run["recording_seconds"]:.6f}s, '
            f'samples {run["first_sample"]}..{run["last_sample"]} (exclusive).</p>'
            + clip(name, first, last) + '</section>')
    result['clips_sha256'] = artifacts
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8">'
        '<title>Physical combat audio: strongest discontinuities</title><style>'
        'body{background:#101821;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto;padding:12px}'
        'a{color:#9df}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:20px}'
        'audio,svg{width:100%}</style><h1>Physical combat: strongest recorded sample steps</h1>'
        '<p>'+html.escape(result['scope'])+'</p>'
        f'<p>{result["seconds"]:g}s; peak {result["peak"]}; '
        f'maximum step {result["max_adjacent_step"]}; clipped samples {result["clipped_samples"]}; '
        f'longest exact-zero run {result["longest_exact_zero_frames"]}/48000 seconds. '
        'Review clips retain original amplitude. Waveform axes use the same full-scale range.</p>'
        '<div class="grid">'+''.join(cards)+'</div>'
        '<h2>Exact-zero intervals</h2><p>Up to eight longest intervals of at least10ms; '
        'all intervals and exact sample counts retained in the report. These may be '
        'intentional musical rests or transitions, not necessarily dropouts.</p>'
        '<div class="grid">'+''.join(quiet_cards)+'</div>'
        '<p><a href="report.json">Exact sample locations, hashes and sensitivity checks</a></p>')
    print(json.dumps({k: result[k] for k in ('max_adjacent_step', 'longest_exact_zero_frames',
        'clipped_samples', 'sensitivity_controls')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio', type=Path, required=True)
    parser.add_argument('--offset', type=float, required=True)
    parser.add_argument('--out', type=Path, required=True)
    audit(**vars(parser.parse_args()))
