"""Bound pulse-retrigger transients against an executed NES reference."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import shutil
import wave

import numpy as np


EVENT_FRAMES = (32, 64, 96, 192, 224)
FULL_SCALE = 32768.0
STEP_RATIO_MARGIN = .02
FULL_SCALE_MARGIN = .005
MAX_NEAR_ZERO_MS = .5


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _longest_run(mask):
    edges = np.flatnonzero(np.diff(np.r_[False, mask, False]))
    return int(max(edges[1::2] - edges[::2], default=0))


def measure(pcm, timeline, rate):
    pcm = np.asarray(pcm)
    if pcm.ndim != 2 or pcm.shape[1] != 2 or len(pcm) < 2 or rate <= 0:
        raise ValueError('Need nonempty stereo PCM at a positive rate')
    if timeline[-1]['end_sample'] != len(pcm):
        raise ValueError('Incomplete waveform timeline')
    peak = np.max(np.abs(pcm.astype(np.int64)), axis=0)
    if min(peak) <= 0:
        raise ValueError('Silent source cannot characterize a transient')
    events = []
    for frame in EVENT_FRAMES:
        rows = [row for row in timeline if row['driver_frame'] == frame]
        if len(rows) != 1 or rows[0]['phase'] not in (0, 2):
            raise ValueError('Missing, duplicate or wrong-phase reset event')
        row = rows[0]
        start, end = row['start_sample'], row['end_sample']
        if not 0 < start < end <= len(pcm):
            raise ValueError('Invalid event sample interval')
        samples = pcm[start:end].astype(np.int64)
        steps = np.abs(np.diff(pcm[start-1:end].astype(np.int64), axis=0))
        max_step = np.max(steps, axis=0)
        near_zero = [_longest_run(np.abs(samples[:, channel]) < 32) * 1000 / rate
                     for channel in range(2)]
        previous = timeline[timeline.index(row)-1]
        prior = pcm[previous['start_sample']:start].astype(np.int64)
        prior_step = np.max(np.abs(np.diff(prior, axis=0)), axis=0)
        events.append(dict(
            frame=frame, start_sample=start, end_sample=end,
            max_step=max_step.tolist(),
            max_step_to_signal_peak=(max_step/peak).tolist(),
            max_step_to_full_scale=(max_step/FULL_SCALE).tolist(),
            local_step_amplification=(max_step/np.maximum(prior_step, 1)).tolist(),
            longest_near_zero_ms=near_zero))
    return dict(
        sample_rate=rate, samples=len(pcm), signal_peak=peak.tolist(),
        clipped_fraction=float(np.mean(np.abs(pcm.astype(np.int64)) >= 32767)),
        max_step_to_signal_peak=max(max(event['max_step_to_signal_peak']) for event in events),
        max_step_to_full_scale=max(max(event['max_step_to_full_scale']) for event in events),
        max_local_step_amplification=max(max(event['local_step_amplification']) for event in events),
        longest_near_zero_ms=max(max(event['longest_near_zero_ms']) for event in events),
        events=events)


def evaluate(reference, candidate):
    limits = dict(
        max_step_to_signal_peak=reference['max_step_to_signal_peak'] + STEP_RATIO_MARGIN,
        max_step_to_full_scale=reference['max_step_to_full_scale'] + FULL_SCALE_MARGIN,
        longest_near_zero_ms=max(MAX_NEAR_ZERO_MS, reference['longest_near_zero_ms']))
    gates = [
        dict(gate='step_relative_to_signal_peak',
             passed=candidate['max_step_to_signal_peak'] <= limits['max_step_to_signal_peak'],
             candidate=candidate['max_step_to_signal_peak'], limit=limits['max_step_to_signal_peak']),
        dict(gate='step_relative_to_pcm_full_scale',
             passed=candidate['max_step_to_full_scale'] <= limits['max_step_to_full_scale'],
             candidate=candidate['max_step_to_full_scale'], limit=limits['max_step_to_full_scale']),
        dict(gate='event_dropout',
             passed=candidate['longest_near_zero_ms'] <= limits['longest_near_zero_ms'],
             candidate_ms=candidate['longest_near_zero_ms'], limit_ms=limits['longest_near_zero_ms']),
        dict(gate='pcm_clipping', passed=candidate['clipped_fraction'] == 0,
             candidate=candidate['clipped_fraction'], limit=0),
    ]
    return gates, limits


def _mutated_controls(pcm, timeline, rate, reference):
    first = next(row for row in timeline if row['driver_frame'] == EVENT_FRAMES[0])
    spike = pcm.copy()
    at = first['start_sample'] + 2
    spike[at] = -32768
    spike[at+1] = 32767
    spike_measure = measure(spike, timeline, rate)
    spike_gates, _ = evaluate(reference, spike_measure)
    dropout = pcm.copy()
    count = max(1, round(rate*.001))
    at = first['start_sample'] + (first['end_sample']-first['start_sample'])//2
    dropout[at:at+count] = 0
    dropout_measure = measure(dropout, timeline, rate)
    dropout_gates, _ = evaluate(reference, dropout_measure)
    return {
        'full_scale_spike': dict(rejected=not all(g['passed'] for g in spike_gates), gates=spike_gates),
        'one_ms_dropout': dict(rejected=not all(g['passed'] for g in dropout_gates), gates=dropout_gates),
    }


def _load(root, name, selected_pulse2):
    report_path, wav_path, timeline_path = (root/'report.json', root/'audio.wav', root/'timeline.json')
    report = json.loads(report_path.read_text())
    expected_profile = 'periodic-retrigger-control' if name == 'nes_control' else 'periodic-retrigger'
    if not report.get('passed') or report.get('profile') != expected_profile:
        raise ValueError('Wrong or failed source profile')
    pulse2 = bool(report.get('pulse2', report.get('pulse2_experiment', False)))
    if selected_pulse2 is not None and pulse2 != selected_pulse2:
        raise ValueError('Cannot compare different pulse voices')
    if name == 'reset_spc' and not (report.get('reset_notes_experiment')
                                    and report.get('fast_reset_experiment')):
        raise ValueError('Candidate is not the reset-aware fast SPC profile')
    if name == 'legacy_spc' and report.get('reset_notes_experiment'):
        raise ValueError('Legacy control unexpectedly resets pulse phase')
    if sha(wav_path) != report['wav_sha256'] or sha(timeline_path) != report['timeline_sha256']:
        raise ValueError('Source hash mismatch')
    timeline = json.loads(timeline_path.read_text())
    with wave.open(str(wav_path)) as source:
        if source.getnchannels() != 2 or source.getsampwidth() != 2:
            raise ValueError('Need stereo PCM16')
        rate = source.getframerate()
        pcm = np.frombuffer(source.readframes(source.getnframes()), '<i2').reshape(-1, 2)
    return dict(root=root, report=report, report_sha256=sha(report_path),
                wav_sha256=sha(wav_path), timeline_sha256=sha(timeline_path),
                timeline=timeline, rate=rate, pcm=pcm, pulse2=pulse2,
                measurement=measure(pcm, timeline, rate))


def _plot(pcm, event, peak):
    samples = pcm[event['start_sample']:event['end_sample'], 0].astype(float)
    stride = max(1, len(samples)//500)
    samples = samples[::stride]
    points = ' '.join(f'{i*600/max(1, len(samples)-1):.2f},{55-45*sample/peak:.2f}'
                      for i, sample in enumerate(samples))
    return f'<svg viewBox="0 0 600 110"><polyline fill="none" stroke="cyan" points="{points}"/></svg>'


def audit(sources, out):
    out.mkdir(parents=True, exist_ok=False)
    loaded = {}
    selected_pulse2 = None
    for name, root in sources.items():
        loaded[name] = _load(root, name, selected_pulse2)
        selected_pulse2 = loaded[name]['pulse2']
    reference = loaded['nes']['measurement']
    candidate = loaded['reset_spc']['measurement']
    gates, limits = evaluate(reference, candidate)
    controls = _mutated_controls(loaded['reset_spc']['pcm'], loaded['reset_spc']['timeline'],
                                 loaded['reset_spc']['rate'], reference)
    passed = all(gate['passed'] for gate in gates) and all(case['rejected'] for case in controls.values())
    variants = {}
    cards = []
    for name, source in loaded.items():
        measurement = source['measurement']
        variants[name] = dict(
            **measurement, source_report_sha256=source['report_sha256'],
            wav_sha256=source['wav_sha256'], timeline_sha256=source['timeline_sha256'])
        shutil.copyfile(source['root']/'audio.wav', out/f'{name}.wav')
        cards.append(f'<section><h2>{html.escape(name)}</h2><audio controls src="{name}.wav"></audio>')
        for event in measurement['events']:
            cards.append(f'<h3>Reset frame {event["frame"]}</h3>'
                         + _plot(source['pcm'], event, max(measurement['signal_peak'])))
        cards.append('</section>')
    result = dict(
        schema='rcr-retrigger-transient-audit-v1', passed=passed, release_ready=False,
        pulse2=selected_pulse2, event_frames=list(EVENT_FRAMES), limits=limits, gates=gates,
        sensitivity_controls=controls, variants=variants,
        scope=('Five isolated same-pitch reset callback frames, stereo PCM16. Bounds maximum sample discontinuity and near-zero dropout against an executed NES reference; '
               'not a psychoacoustic verdict, mixed-game SFX/music fidelity, analog-output measurement or proof that no listener can hear a click.'),
        local_step_amplification_note=('Reported for audit but not gated: the SPC and NES paths have different waveform smoothing, so their local edge ratios are not directly equivalent.'))
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    rows = ''.join(f'<tr><td>{html.escape(g["gate"])}</td><td>{g["passed"]}</td></tr>' for g in gates)
    (out/'index.html').write_text(
        '<!doctype html><meta charset="utf-8"><title>RCR retrigger transient audit</title>'
        '<style>body{background:#111;color:#eee;font:16px sans-serif;max-width:1100px;margin:auto}'
        'section{border-top:1px solid #555}svg{width:100%;background:#181818}table{border-collapse:collapse}'
        'td,th{border:1px solid #777;padding:.4em}</style>'
        '<h1>Pulse-retrigger transient audit</h1><p>Unmodified audio, fixed reset frames, both channels measured. '
        'Plots show the left channel for review. This is a bounded digital-signal audit, not a claim of subjective inaudibility.</p>'
        '<p><a href="report.json">Measurements, gates, hashes and negative controls</a></p>'
        f'<table><tr><th>Gate</th><th>Pass</th></tr>{rows}</table>' + ''.join(cards))
    print(json.dumps(dict(passed=passed, pulse2=selected_pulse2, gates=gates,
                          sensitivity_controls={k:v['rejected'] for k,v in controls.items()}), indent=2))
    return passed


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('nes', 'nes_control', 'legacy_spc', 'reset_spc', 'out'):
        parser.add_argument('--'+name.replace('_', '-'), type=Path, required=True)
    args = vars(parser.parse_args())
    out = args.pop('out')
    raise SystemExit(0 if audit(args, out) else 1)
