"""Compare held-out recorded menu audio after a single bounded calibration.

Not a waveform, timbre, click-inaudibility or full-game fidelity oracle.
The first four seconds alone choose one constant lag and channel gains.
No time stretching, per-window realignment or holdout gain fitting is allowed.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path
import wave

import numpy as np


STEP = .01
CALIBRATION_SECONDS = 4


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    with wave.open(str(path)) as stream:
        if stream.getnchannels() != 2 or stream.getsampwidth() != 2:
            raise ValueError('Need stereo signed16 PCM')
        rate = stream.getframerate()
        raw = stream.readframes(stream.getnframes())
        if len(raw) != stream.getnframes()*4 or rate not in (32040, 48000):
            raise ValueError('Incomplete or unsupported PCM')
    return np.frombuffer(raw, '<i2').reshape(-1, 2), rate, raw


def integral(pcm):
    data = pcm.astype(np.float64)
    if data.ndim != 2 or data.shape[1] != 2 or not np.isfinite(data).all():
        raise ValueError('Need finite stereo data')
    return np.vstack((np.zeros(2), np.cumsum(data*data, axis=0)))


def envelope(sums, rate, start, seconds):
    bins = round(seconds/STEP)
    if start < 0 or bins < 1 or abs(bins*STEP-seconds) > 1e-8:
        raise ValueError('Invalid fixed-grid interval')
    edges = np.rint((start+np.arange(bins+1)*STEP)*rate).astype(np.int64)
    if edges[-1] >= len(sums) or np.any(np.diff(edges) <= 0):
        raise ValueError('PCM does not cover comparison interval')
    return np.sqrt((sums[edges[1:]]-sums[edges[:-1]])/np.diff(edges)[:, None])


def correlation(a, b):
    if min(np.std(a), np.std(b)) < 1:
        raise ValueError('Uninformative calibration signal')
    return float(np.corrcoef(a, b)[0, 1])


def calibrate(reference, recorded, reference_rate, recorded_rate, start, expected_lag):
    target = envelope(reference, reference_rate, start, CALIBRATION_SECONDS)
    scores = []
    # Bounded to the independently observed ident handoff neighborhood.
    # Preserve every score, including alternatives: no hidden alignment search.
    for milliseconds in range(-40, 41):
        lag = expected_lag+milliseconds/1000
        actual = envelope(recorded, recorded_rate, start+lag, CALIBRATION_SECONDS)
        score = correlation(target.mean(axis=1), actual.mean(axis=1))
        scores.append(dict(lag=lag, correlation=score))
    best = max(scores, key=lambda x: x['correlation'])
    if best in (scores[0], scores[-1]) or best['correlation'] < .9:
        raise ValueError('No interior menu calibration above 0.9')
    actual = envelope(recorded, recorded_rate, start+best['lag'], CALIBRATION_SECONDS)
    gain = np.sum(target*actual, axis=0)/np.sum(target*target, axis=0)
    if not np.isfinite(gain).all() or np.any(gain <= 0):
        raise ValueError('Invalid channel calibration')
    return dict(lag=best['lag'], gains=gain.tolist(), scores=scores,
                calibration_seconds=CALIBRATION_SECONDS)


def evaluate(expected, actual):
    if expected.shape != actual.shape or len(expected) < 100:
        raise ValueError('Missing holdout coverage')
    # Narrow diagnostic: one 10ms energy bin missing >=80% of a clearly
    # active reference. Smaller pops and filter/timbre differences stay open.
    missing = (expected > 150) & (actual < expected*.2)
    correlations = [correlation(expected[:, c], actual[:, c]) for c in (0, 1)]
    nrmse = np.sqrt(np.mean((expected-actual)**2, axis=0)/np.mean(expected**2, axis=0))
    return dict(passed=not missing.any() and min(correlations) >= .9,
                missing_energy_bins=[dict(bin=int(i), channel=int(c)) for i,c in zip(*np.where(missing))],
                correlations=correlations, normalized_rms_error=nrmse.tolist(), bins=len(expected))


def compare(reference_pcm, recorded_pcm, reference_rate, recorded_rate, start, seconds, expected_lag):
    if seconds < 14:
        raise ValueError('Need four calibration seconds and at least ten held-out seconds')
    ref, rec = integral(reference_pcm), integral(recorded_pcm)
    calibration = calibrate(ref, rec, reference_rate, recorded_rate, start, expected_lag)
    expected = envelope(ref, reference_rate, start, seconds)*calibration['gains']
    actual = envelope(rec, recorded_rate, start+calibration['lag'], seconds)
    first = round(CALIBRATION_SECONDS/STEP)
    result = evaluate(expected[first:], actual[first:])
    return dict(calibration=calibration, holdout=result,
                envelope_expected=expected.tolist(), envelope_recorded=actual.tolist())


def sensitivity(reference_pcm, recorded_pcm, reference_rate, recorded_rate, start, seconds, result):
    """Execute PCM mutants in the held-out region without refitting calibration."""
    first = round(CALIBRATION_SECONDS/STEP)
    expected = np.asarray(result['envelope_expected'])[first:]
    # Select the strongest actual reference bin, not a convenient silent note.
    index = int(np.argmax(np.min(expected, axis=1)))
    if np.min(expected[index]) <= 150:
        raise ValueError('No active holdout energy for sensitivity controls')
    lag = result['calibration']['lag']
    begin = round((start+lag+(first+index)*STEP)*recorded_rate)
    controls = {}
    for name, channel, duration in (('10ms_both', None, .01), ('20ms_left', 0, .02), ('50ms_right', 1, .05)):
        altered = recorded_pcm.copy()
        end = min(len(altered), begin+round(duration*recorded_rate))
        if channel is None:
            altered[begin:end] = 0
        else:
            altered[begin:end, channel] = 0
        actual = envelope(integral(altered), recorded_rate, start+lag, seconds)[first:]
        checked = evaluate(expected, actual)
        controls[name] = dict(rejected=not checked['passed'], begin_sample=begin,
                              end_sample=end, channel=channel, result=checked)
    # A clock discontinuity after calibration must not be hidden by realignment.
    altered = recorded_pcm.copy()
    at = round((start+lag+CALIBRATION_SECONDS+1)*recorded_rate)
    shift = round(.1*recorded_rate)
    altered[at+shift:] = recorded_pcm[at:-shift]
    altered[at:at+shift] = 0
    actual = envelope(integral(altered), recorded_rate, start+lag, seconds)[first:]
    checked = evaluate(expected, actual)
    controls['100ms_clock_slip'] = dict(rejected=not checked['passed'], result=checked)
    return controls


def audit(reference, recorded, receipt, rom, ident_report, record_offset, start, seconds, out):
    proof = json.loads(receipt.read_text())
    ident = json.loads(ident_report.read_text())
    a, ar, raw = load(reference)
    b, br, _ = load(recorded)
    if (proof.get('rom_sha256') != sha(rom) or proof.get('input_profile') != 'title'
            or proof.get('status') != 'passed' or proof['sample_rate'] != ar
            or proof['audio_pcm_sha256'] != hashlib.sha256(raw).hexdigest()
            or not ident['passed'] or ident['source']['rom_sha256'] != sha(rom)):
        raise ValueError('Unbound ROM, no-input reference or hardware ident')
    # First 10ms above40 PCM locates the reference ident, not a fitted song beat.
    levels = envelope(integral(a), ar, 0, 6).mean(axis=1)
    active = np.flatnonzero(levels > 40)
    if not len(active) or not 0.5 < active[0]*STEP < 2:
        raise ValueError('Unexpected reference ident onset')
    ident_lag = ident['hardware_note_start_seconds_into_recording']-record_offset-active[0]*STEP
    result = compare(a, b, ar, br, start, seconds, ident_lag)
    controls = sensitivity(a, b, ar, br, start, seconds, result)
    report = dict(diagnostic_passed=result['holdout']['passed'] and all(x['rejected'] for x in controls.values()),
        release_ready=False, reference_start_seconds=start, seconds=seconds,
        recorded_extraction_offset=record_offset, initial_ident_lag=ident_lag,
        scope='One constant lag within +/-40ms of ident alignment and two gains fitted only on '
              'the first four menu seconds. At least ten held-out seconds, no time stretching '
              'or holdout fitting. Energy/dropout and coarse cadence diagnostic, not waveform '
              'fidelity, absence of smaller clicks, subjective sound quality or full-game speed. '
              'Recording extraction offset is supplied metadata; no immutable historical OBS routing claim.',
        result=result, controls=controls,
        sources={str(p):sha(p) for p in (Path(__file__), reference, recorded, receipt, rom, ident_report)})
    out.mkdir(parents=True, exist_ok=False)
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    import os
    link = lambda p:html.escape(os.path.relpath(p, out))
    curves = []
    expected = np.asarray(result['envelope_expected'])[:, 0]
    actual = np.asarray(result['envelope_recorded'])[:, 0]
    ceiling = max(expected.max(), actual.max(), 1)
    for values, color in ((expected, '#60dfff'), (actual, '#ff80b5')):
        points=' '.join(f'{i*1000/(len(values)-1):.2f},{190-v/ceiling*170:.2f}'
                        for i,v in enumerate(values))
        curves.append(f'<polyline fill="none" stroke="{color}" stroke-width="1" points="{points}"/>')
    chart = ('<h2>Left-channel 10ms energy envelope</h2><p>Cyan: calibrated emulator; pink: recording. '
        'Shaded first four seconds are calibration; all remaining bins are held out. '
        'Every bin is plotted, with no smoothing. Both channels are checked in the report.</p>'
        '<svg viewBox="0 0 1000 210" role="img" aria-label="Menu energy envelope comparison">'
        f'<rect width="{1000*CALIBRATION_SECONDS/seconds:.2f}" height="210" fill="#344252"/>'
        +''.join(curves)+'</svg>')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Held-out MiSTer menu audio</title>'
        '<style>body{background:#101821;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}'
        'a{color:#9df}audio{width:100%}pre{white-space:pre-wrap}</style><h1>Held-out MiSTer menu audio</h1><p>'
        +html.escape(report['scope'])+'</p><h2>Original physical recording</h2>'
        f'<audio controls src="{link(recorded)}"></audio><h2>Unmodified emulator reference</h2>'
        f'<audio controls src="{link(reference)}"></audio><p>No audio processing applied to these listening files.</p>'
        +chart+
        '<pre>'+html.escape(json.dumps(dict(calibration=result['calibration'], holdout=result['holdout'],
            controls=controls),indent=2))+'</pre><a href="report.json">All bins, source hashes and controls</a>')
    print(json.dumps(dict(diagnostic_passed=report['diagnostic_passed'], lag=result['calibration']['lag'],
        holdout=result['holdout'], controls={k:v['rejected'] for k,v in controls.items()}), indent=2))
    return report


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('reference','recorded','receipt','rom','ident-report','out'):
        p.add_argument('--'+name, type=Path, required=True)
    for name in ('record-offset','start','seconds'):
        p.add_argument('--'+name, type=float, required=True)
    audit(**vars(p.parse_args()))
