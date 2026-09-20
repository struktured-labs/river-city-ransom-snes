"""Fail-closed pause/resume liveness audit for paired baseline captures.

This is deliberately narrower than an audio-fidelity or full-speed verdict.  It
detects the scheduler failure where a retained original-game NMI leaves $4200
masked and the main thread stranded in RCR's F2C9 tick wait.
"""
import argparse
import json
from pathlib import Path

try:
    from .benchmark_report import POLICY, sha, verify_capture
except ImportError:
    from benchmark_report import POLICY, sha, verify_capture


PHASES = ('press_pause', 'pause_requested', 'press_resume', 'resume_requested')


def _phase(rows, name):
    selected = [row for row in rows if row['phase'] == name]
    if not selected:
        raise ValueError(f'Missing {name} phase')
    return selected


def _changes(rows, key):
    return sum(a[key] != b[key] for a, b in zip(rows, rows[1:]))


def _audio_fraction(rows):
    return sum(row['audio']['ac_rms'] > POLICY['active_ac_rms'] for row in rows) / len(rows)


def _nmi_delta(rows):
    counters = [row.get('nmi_counter') for row in rows]
    if any(not isinstance(value, int) for value in counters):
        return None
    if any(b < a for a, b in zip(counters, counters[1:])):
        return -1
    return counters[-1] - counters[0]


def metrics(rows):
    result = {}
    for name in PHASES:
        phase = _phase(rows, name)
        result[name] = {
            'frames': len(phase),
            'input_frames_requested': sum(bool(row['input_requested']) for row in phase),
            'input_frames_delivered': sum(row['input_requested'] == row['input_delivered']
                                          and bool(row['input_requested']) for row in phase),
            'ram_changes': _changes(phase, 'ram_sha256'),
            'video_changes': _changes(phase, 'video_sha256'),
            'active_audio_fraction': _audio_fraction(phase),
            'nmi_delta': _nmi_delta(phase),
        }
    native = _phase(rows, 'resume_requested')[-1].get('native') or {}
    result['deferred_end'] = {
        key: native.get(key) for key in (
            'deferred_game_nmi_pending', 'deferred_game_nmi_scheduled',
            'deferred_game_nmi_served', 'deferred_game_nmi_fallback')
    }
    return result


def analyze(reference_rows, candidate_rows):
    reference = metrics(reference_rows)
    candidate = metrics(candidate_rows)
    pause_ref = reference['pause_requested']
    pause = candidate['pause_requested']
    resume_ref = reference['resume_requested']
    resume = candidate['resume_requested']
    deferred = candidate['deferred_end']
    gates = [
        {
            'gate': 'pause_and_resume_input_delivered',
            'passed': all(candidate[name]['input_frames_requested'] > 0
                          and candidate[name]['input_frames_requested'] == candidate[name]['input_frames_delivered']
                          for name in ('press_pause', 'press_resume')),
        },
        {
            'gate': 'pause_nmi_liveness',
            'passed': pause['nmi_delta'] is not None
                      and pause['nmi_delta'] >= pause['frames'] - 2,
        },
        {
            'gate': 'pause_ram_liveness',
            'passed': pause['ram_changes'] >= int((pause['frames'] - 1) * 0.90),
        },
        {
            'gate': 'pause_visual_cadence',
            'passed': pause_ref['video_changes'] > 0
                      and abs(pause['video_changes'] - pause_ref['video_changes']) <= 1,
        },
        {
            'gate': 'resume_nmi_liveness',
            'passed': resume['nmi_delta'] is not None
                      and resume['nmi_delta'] >= resume['frames'] - 2,
        },
        {
            'gate': 'resume_ram_liveness',
            'passed': resume['ram_changes'] >= int((resume['frames'] - 1) * 0.90),
        },
        {
            'gate': 'resume_video_liveness',
            'passed': resume_ref['video_changes'] > 0
                      and resume['video_changes'] >= resume_ref['video_changes'] * 0.50,
        },
        {
            'gate': 'resume_audio_presence',
            'passed': resume_ref['active_audio_fraction'] >= POLICY['reference_active_fraction']
                      and resume['active_audio_fraction'] >= POLICY['minimum_candidate_active_fraction'],
        },
        {
            'gate': 'deferred_nmi_drained',
            'passed': deferred['deferred_game_nmi_pending'] == 0
                      and deferred['deferred_game_nmi_scheduled'] is not None
                      and deferred['deferred_game_nmi_scheduled'] == deferred['deferred_game_nmi_served'],
        },
        {
            'gate': 'pause_path_needs_no_fallback',
            'passed': deferred['deferred_game_nmi_fallback'] == 0,
        },
    ]
    return {
        'schema': 'rcr-pause-resume-audit-v1',
        'scope': ('Deadlock/liveness and coarse audio-presence only; this does not certify '
                  'music/SFX fidelity, perceptual pop freedom, or full-game speed.'),
        'passed': all(gate['passed'] for gate in gates),
        'gates': gates,
        'reference': reference,
        'candidate': candidate,
    }


def build(reference_dir, candidate_dir, out):
    reference, reference_rows = verify_capture(reference_dir)
    candidate, candidate_rows = verify_capture(candidate_dir)
    if (reference['system'], candidate['system']) != ('nes', 'snes'):
        raise ValueError('Pause/resume audit requires NES reference and SNES candidate')
    if reference.get('scenario_name') != 'baseline' or candidate.get('scenario_name') != 'baseline':
        raise ValueError('Pause/resume audit requires baseline scenarios')
    if not reference['capture_complete'] or not candidate['capture_complete']:
        raise ValueError('Pause/resume audit requires complete captures')
    if any(row['fault'] for row in reference_rows + candidate_rows):
        raise ValueError('Adapter fault in capture')
    result = analyze(reference_rows, candidate_rows)
    result['reference_capture_sha256'] = sha(reference_dir / 'capture.json')
    result['candidate_capture_sha256'] = sha(candidate_dir / 'capture.json')
    result['tool_sha256'] = sha(Path(__file__))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'out': str(out), 'passed': result['passed'],
                      'failed': [gate['gate'] for gate in result['gates'] if not gate['passed']]}))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if build(args.reference, args.candidate, args.out)['passed'] else 1)
