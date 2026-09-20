"""Identical-command restart A/B: preserve every event, including worse sample steps."""
import argparse
import html
import json
from pathlib import Path
import wave

import numpy as np

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha


def events(rows):
    previous, duty, result = 0, [0, 0], []
    for frame, row in enumerate(rows, 1):
        if row['source_frame'] != frame:
            raise ValueError('Missing source frame')
        count = row['packets']
        if count == previous:
            continue
        if count != previous+1:
            raise ValueError('Missing packet')
        previous = count
        packet = bytes.fromhex(row['packet'])
        if len(packet) != 23:
            raise ValueError('Malformed packet')
        mask = packet[22] & packet[21] & 3
        for voice in (0, 1):
            if packet[21] & (1 << voice):
                current = packet[voice*4] >> 6
                if current != duty[voice]:
                    mask |= 1 << voice
                duty[voice] = current
        if mask:
            result.append(dict(frame=frame, packet=count, voices=mask))
    return result


def measures(pcm, rows, requested):
    if pcm.ndim != 2 or pcm.shape[1] != 2:
        raise ValueError('Need stereo PCM')
    result = []
    for event in requested:
        row = rows[event['frame']-1]
        first, last = row['start_sample'], row['end_sample']
        if not 0 < first < last <= len(pcm):
            raise ValueError('Incomplete event callback')
        segment = pcm[first-1:last].astype(np.int32)
        result.append(dict(**event, start_sample=first, end_sample=last,
            maximum_step=int(np.abs(np.diff(segment, axis=0)).max())))
    return result


def audit(baseline, candidate, original_fixture, changed_fixture, out):
    fixtures = [bound_report(p/'manifest.json') for p in (original_fixture, changed_fixture)]
    if (sha(original_fixture/'stream.bin') != sha(changed_fixture/'stream.bin') or
            fixtures[0]['source_frames'] != fixtures[1]['source_frames'] or
            fixtures[0]['packets'] != fixtures[1]['packets']):
        raise ValueError('Different command stream')
    recordings, reports = {}, {}
    for name, directory, fixture in [('baseline', baseline, fixtures[0]), ('candidate', candidate, fixtures[1])]:
        report = bound_report(directory/'report.json')
        if not report['passed']:
            raise ValueError('Incomplete replay')
        expected_rom = original_fixture/'player.sfc' if name == 'baseline' else changed_fixture/'player.sfc'
        if report['sources'].get(str(expected_rom)) != fixture['rom_sha256']:
            raise ValueError('Replay is not bound to requested fixture')
        rows = json.loads((directory/'timeline.json').read_text())
        with wave.open(str(directory/'audio.wav')) as f:
            if f.getnchannels() != 2 or f.getsampwidth() != 2:
                raise ValueError('Need stereo PCM16')
            rate = f.getframerate()
            pcm = np.frombuffer(f.readframes(f.getnframes()), '<i2').reshape(-1, 2)
        recordings[name] = (rate, pcm, rows)
        reports[name] = report
    a, b = recordings['baseline'], recordings['candidate']
    input_fields = ('source_frame', 'host_frame', 'packets', 'packet')
    if (a[0] != b[0] or len(a[2]) != len(b[2]) or len(a[1]) != len(b[1]) or
            any(any(x[k] != y[k] for k in input_fields) for x, y in zip(a[2], b[2]))):
        raise ValueError('Inputs, host frames, total PCM length or rates differ; no fitted alignment allowed')
    boundaries = [dict(source_frame=x['source_frame'], start_delta=y['start_sample']-x['start_sample'],
                      end_delta=y['end_sample']-x['end_sample']) for x, y in zip(a[2], b[2])
                  if (x['start_sample'], x['end_sample']) != (y['start_sample'], y['end_sample'])]
    requested = events(a[2])
    if not requested:
        raise ValueError('No pulse restarts')
    measured = {name: measures(pcm, rows, requested) for name, (_, pcm, rows) in recordings.items()}
    comparison = [dict(frame=x['frame'], packet=x['packet'], voices=x['voices'],
        baseline=x['maximum_step'], candidate=y['maximum_step'],
        difference=y['maximum_step']-x['maximum_step'])
        for x, y in zip(measured['baseline'], measured['candidate'])]
    summary = dict(events=len(comparison), improved=sum(e['difference'] < 0 for e in comparison),
        unchanged=sum(e['difference'] == 0 for e in comparison), worsened=sum(e['difference'] > 0 for e in comparison),
        baseline_event_max=max(e['baseline'] for e in comparison), candidate_event_max=max(e['candidate'] for e in comparison))
    # One-sample full-scale disturbance is a measurement control, not a game
    # mutation and not a psychoacoustic pop threshold.
    damaged = a[1].copy()
    at = a[2][requested[0]['frame']-1]['start_sample']+2
    damaged[at:at+2] = [[-32768, -32768], [32767, 32767]]
    injected = measures(damaged, a[2], requested)[0]['maximum_step'] == 65535
    if not injected:
        raise ValueError('Sample spike was missed')
    out.mkdir(parents=True, exist_ok=False)
    cards, artifacts = [], {}
    selected = [('largest step increases', sorted(comparison, key=lambda e: -e['difference'])[:3]),
                ('largest step decreases', sorted(comparison, key=lambda e: e['difference'])[:3])]
    for label, selection in selected:
        cards.append('<h2>'+label+'</h2>')
        for event in selection:
            frame = event['frame']
            cards.append(f'<section><h3>Source frame {frame}: {event["baseline"]} → {event["candidate"]}</h3>')
            for name, (rate, pcm, rows) in recordings.items():
                first = rows[max(0, frame-16)]['start_sample']
                last = rows[min(len(rows)-1, frame+14)]['end_sample']
                target = f'{name}-{frame}.wav'
                with wave.open(str(out/target), 'wb') as f:
                    f.setparams((2, 2, rate, 0, 'NONE', 'not compressed'))
                    f.writeframes(pcm[first:last].tobytes())
                artifacts[target] = sha(out/target)
                cards.append(f'<p>{name} · original amplitude/rate</p><audio controls src="{target}"></audio>')
            cards.append('</section>')
    sources = {str(p): sha(p) for p in (Path(__file__), Path('tools/audit_main_display_latency.py'),
        baseline/'report.json', candidate/'report.json', original_fixture/'manifest.json', changed_fixture/'manifest.json')}
    result = dict(summary=summary, events=comparison, identical_host_frame_inputs=True, identical_stream=True,
        callback_boundary_differences=boundaries, identical_callback_boundaries=not boundaries,
        injected_spike_detected=injected, sources=sources, artifacts=artifacts,
        sample_rate=a[0], pop_free_verified=False, waveform_improvement_verified=False,
        scope='Same complete packet stream, host frames, sample rate and total PCM length. Callback '
        'sample boundaries can differ and every difference is reported; each run uses its own '
        'recorded callback boundaries, without fitted alignment. All pulse-reset/duty '
        'callbacks measured, not only improved events. Maximum adjacent sample step over each whole '
        'callback includes other channels and natural pulse/noise edges; it is not an identified pop '
        'or a perceptual ranking. PCM clips are neither normalized nor shifted/resampled.')
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Pulse restart A/B</title>'
        '<style>body{background:#101821;color:#eef;font:17px system-ui;max-width:1000px;margin:25px auto}'
        'a{color:#9df}section{border:1px solid #567;padding:12px;margin:12px 0}audio{width:100%}</style>'
        '<h1>Pulse restart order: mixed audio result</h1><p>'+html.escape(result['scope'])+'</p><pre>'+
        html.escape(json.dumps(summary, indent=2))+'</pre><p>Ordering fix is not yet an audible-pop fix. '
        'Not deployed to Rival.</p><p><a href="report.json">All events and source hashes</a></p>'+''.join(cards))
    print(json.dumps(summary))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline', 'candidate', 'original-fixture', 'changed-fixture', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    audit(**vars(p.parse_args()))
