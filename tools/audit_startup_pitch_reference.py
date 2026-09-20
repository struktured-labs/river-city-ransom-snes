"""Retain the existing eight NES transient gates for the startup-pitch trial."""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from tools.audit_current_pulse_reference import measure
from tools.audit_main_display_latency import bound_report
from tools.audit_retrigger_transient import evaluate
from tools.benchmark_report import sha
from tools.review_native_transient_stems import same_core_load


def audit(reference, qualification, baseline, trial, fixture, baseline_observed, trial_observed, out):
    if out.exists():
        raise ValueError('Fresh reference comparison required')
    original = bound_report(reference/'report.json')
    proof = bound_report(qualification/'report.json')
    cases = [c['case'] for c in original['cases']]
    sources = dict(original['sources'], **proof['sources'])
    measurements = {}
    for name, normal, observed in [('baseline', baseline, baseline_observed), ('trial', trial, trial_observed)]:
        spec = bound_report(fixture/name/'manifest.json')
        if spec['cases'] != cases:
            raise ValueError('Different held-tone/reset stimuli')
        onset, _, _, _ = same_core_load(observed, normal, fixture/name)
        if onset['restarts'] != 32 or onset['wrong_first_pitch'] or onset['stale_nonzero_onsets']:
            raise ValueError('Wrong reset schedule or initial pitch')
        rate, pcm = wavfile.read(normal/'audio.wav')
        if rate != 32040 or pcm.dtype != np.int16 or pcm.ndim != 2 or pcm.shape[1] != 2:
            raise ValueError('Wrong native PCM')
        rows = json.loads((normal/'timeline.json').read_text())
        measurements[name] = []
        for old in original['cases']:
            result = measure(pcm, rate, rows, old['case'])
            gates, limits = evaluate(old['measurements']['nes'], result)
            if not result['fundamental']['passed']:
                raise ValueError('Incorrect or missing tone fundamental')
            measurements[name].append(dict(case=old['case'], measurements=result,
                nes=old['measurements']['nes'], gates=gates, limits=limits,
                passed=all(g['passed'] for g in gates)))
        for p in (fixture/name/'manifest.json', normal/'report.json', normal/'audio.wav',
                  normal/'timeline.json', observed/'onset-observer.json'):
            sources[str(p)] = sha(p)
    paths = [Path(__file__), Path('tools/audit_current_pulse_reference.py'),
             Path('tools/audit_retrigger_transient.py'), Path('tools/check_nes_disabled_reload.py'),
             reference/'report.json', qualification/'report.json']
    sources.update({str(p): sha(p) for p in paths})
    result = dict(measurements=measurements, sources=sources,
        passed_cases={name: sum(c['passed'] for c in cases) for name, cases in measurements.items()},
        all_original_bounds_passed=all(c['passed'] for c in measurements['trial']),
        scope=__doc__+' Native callback windows without gain, phase, onset or sample-rate fitting. '
              'Held periods do not establish changing-note waveform fidelity or perceptual improvement.',
        release_ready=False, physical_audio_verified=False)
    out.mkdir()
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(passed_cases=result['passed_cases'], all_original_bounds_passed=result['all_original_bounds_passed'])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('reference', 'qualification', 'baseline', 'trial', 'fixture', 'baseline-observed', 'trial-observed', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    audit(**vars(p.parse_args()))
