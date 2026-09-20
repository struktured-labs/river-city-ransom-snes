"""Execute word-pitch equivalence, timing, replay and full-game regression gates."""
import argparse
from collections import Counter
import json
from pathlib import Path

from tools.audit_balanced_pitch_timing import records
from tools.audit_main_display_latency import bound_report
from tools.audit_pulse_onset import load
from tools.audit_pulse_pitch import pitch_updates
from tools.benchmark_report import sha, verify_capture
from tools.build_word_pitch_trial import patch
from tools.check_inline_pitch_trial import run
from tools.check_pitch_pair_trial import run_cases
from tools.check_receiver_poll_trial import stream


def compare_writes(before, after):
    if not before or len(before) != len(after):
        raise ValueError('Different DSP write counts')
    shifts = {}
    for voice in (0, 1):
        for pair in pitch_updates(before, voice):
            gap = pair['high']['tick'] - pair['low']['tick']
            if gap == 8:
                shifts[pair['low']['tick']] = 3
            elif not (pair['low']['packet'] == pair['high']['packet'] == 0 and gap in (10, 20, 21)):
                raise ValueError('Unknown baseline pitch transaction')
    if not shifts:
        raise ValueError('No live pitch transactions')
    counts = Counter()
    for a, b in zip(before, after):
        if any(a[k] != b[k] for k in ('register', 'value', 'packet')):
            raise ValueError('DSP command value/order changed')
        delta = b['tick'] - a['tick']
        if delta != shifts.get(a['tick'], 0):
            raise ValueError('Unexpected DSP command time change')
        counts[delta] += 1
    return dict(writes=len(before), shifts=dict(counts), live_pitch_gap_before=8, live_pitch_gap_after=5)


def compare_game(before, after):
    if len(before) != len(after) or not before:
        raise ValueError('Different or empty game coverage')
    state, callbacks = [], []
    for a, b in zip(before, after):
        fields = (set(a) | set(b)) - {'audio', 'audio_start_sample'}
        changed = [k for k in sorted(fields) if a.get(k) != b.get(k)]
        if changed:
            state.append(dict(frame=a['frame'], fields=changed))
        if (a['audio_start_sample'], a['audio']['samples']) != (b['audio_start_sample'], b['audio']['samples']):
            callbacks.append(dict(frame=a['frame'], before=[a['audio_start_sample'], a['audio']['samples']],
                                  after=[b['audio_start_sample'], b['audio']['samples']]))
    return dict(frames=len(before), state_errors=state, callback_changes=callbacks,
                strict_passed=not state and not callbacks)


def check(trial, core, baseline_observed, trial_observed, baseline_normal,
          trial_normal, game_parent, game_trial, out):
    if out.exists():
        raise ValueError('Need fresh output')
    bound_report(trial/'report.json')
    manifest = json.loads((trial/'game/manifest.json').read_text())
    layout = manifest['sweep_driver_layout']
    engines = [(trial/side/'engine.bin').read_bytes() for side in ('baseline', 'trial')]
    rebuilt, metadata = patch(engines[0], layout)
    if rebuilt != engines[1]:
        raise ValueError('Different patch bytes')
    a, b = [run(core, e, layout) for e in engines]
    errors = [i for i, (x, y) in enumerate(zip(a, b)) if x[0] != y[0]]
    deltas = sorted({y[1]-x[1] for x, y in zip(a, b)})
    wrong = bytearray(engines[1])
    for change in metadata['changes']:
        at = change['offset'] + len(bytes.fromhex(change['after'])) - 10
        if wrong[at] != 0xfd:
            raise ValueError('Missing high-byte prefetch mutation site')
        wrong[at] = 0x00  # NOP instead of MOV Y,A; writes index rather than pitch high.
    good, mutant = [run_cases(core, e, layout) for e in (engines[0], bytes(wrong))]
    rejected = sum(x[0] != y[0] for x, y in zip(good, mutant))
    continuous = {name: [stream(core, engine, layout, mode, delay) for mode in (0, 128)
                        for delay in (0, 256, 512, 2048)]
                  for name, engine in zip(('baseline', 'trial'), engines)}
    onsets, traces, paths = [], [], []
    for side, observed, normal in (('baseline', baseline_observed, baseline_normal),
                                   ('trial', trial_observed, trial_normal)):
        onset, _, _, _ = load(observed, normal, trial/side)
        onsets.append({k: onset[k] for k in ('observer_neutral', 'raw_dac_identical',
                      'received_packets', 'wrong_first_pitch', 'stale_nonzero_onsets')})
        binding = bound_report(observed/'onset-observer.json')
        trace = Path(binding['traces']['RCR_DSP_LATENCY_TRACE'])
        paths.extend([observed/'onset-observer.json', normal/'report.json', trace])
        traces.append(records(trace))
    timing = compare_writes(traces[0][0], traces[1][0])
    receipts_equal = all(traces[0][1][kind] == traces[1][1][kind] for kind in ('P', 'R'))
    p, rows = verify_capture(game_parent)
    q, changed = verify_capture(game_trial)
    if (not p['capture_complete'] or not q['capture_complete'] or p['scenario_sha256'] != q['scenario_sha256']
            or p['rom_sha256'] != json.loads((trial/'baseline/manifest.json').read_text())['source_rom_sha256']
            or q['rom_sha256'] != sha(trial/'game/native-cpu.sfc')):
        raise ValueError('Different/incomplete full-game captures')
    game = compare_game(rows, changed)
    controls = {}
    at = next(i for i, (x, y) in enumerate(zip(traces[0][0], traces[1][0])) if x['tick'] != y['tick'])
    for name, key in (('wrong_pitch', 'value'), ('wrong_time', 'tick')):
        bad = [dict(x) for x in traces[1][0]]
        bad[at][key] += 1
        try:
            compare_writes(traces[0][0], bad)
            controls[name] = False
        except ValueError:
            controls[name] = True
    passed = (not errors and deltas == [0] and rejected > 0 and receipts_equal and game['strict_passed']
              and all(controls.values()) and all(not r['wrong_first_pitch'] and not r['stale_nonzero_onsets'] for r in onsets)
              and all(r['passed'] and not r['bad_volume_writes'] for side in continuous.values() for r in side))
    paths += [Path(__file__), Path('tools/build_word_pitch_trial.py'), Path('tools/check_inline_pitch_trial.py'),
              Path('tools/check_pitch_pair_trial.py'), Path('tools/check_receiver_poll_trial.py'),
              Path('tools/check_sweep_driver.py'), Path('tools/spc_sweep_driver_probe.inc'),
              Path('tools/audit_pulse_onset.py'), Path('tools/audit_pulse_pitch.py'),
              Path('tools/audit_balanced_pitch_timing.py'), core, trial/'report.json',
              trial/'baseline/engine.bin', trial/'trial/engine.bin', game_parent/'capture.json', game_trial/'capture.json']
    paths += [core.parent.parent/'apu/bapu/smp'/name for name in ('core.cpp', 'smp.cpp', 'memory.cpp', 'timing.cpp')]
    report = dict(passed=passed, cases=len(a), state_errors=errors, added_spc_clocks=deltas,
                  wrong_high_mutant_failures=rejected, continuous=continuous, onsets=onsets, timing=timing,
                  receipt_ready_equal=receipts_equal, game=game, controls=controls,
                  sources={str(p): sha(p) for p in paths}, scope=__doc__, deployed=False, pop_free_verified=False)
    out.mkdir(parents=True, exist_ok=False)
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ('passed', 'cases', 'state_errors', 'added_spc_clocks',
                     'wrong_high_mutant_failures', 'timing', 'receipt_ready_equal', 'game', 'controls')}))
    if not passed:
        raise ValueError('Word-pitch regression gate failed; evidence retained')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('trial', 'core', 'baseline-observed', 'trial-observed', 'baseline-normal',
                 'trial-normal', 'game-parent', 'game-trial', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    check(**vars(parser.parse_args()))
