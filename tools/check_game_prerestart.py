"""Observe current-game pulse setup before hardware KON; not a perceptual verdict."""
import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
from scipy.io import wavfile

from tools.audit_main_display_latency import bound_report
from tools.audit_postpublish_keyon import load
from tools.audit_pulse_onset import parse_voice
from tools.audit_pulse_pitch import pitch_updates, sample_expectation
from tools.audit_voice_edges import parse, registers, validate_group
from tools.benchmark_report import sha, verify_capture
from tools.capture_combat_instructions import equivalent


def select(events):
    """Fixed timing-only selection: long setups by changed field plus short controls."""
    chosen = {}
    for voice in (0, 1):
        eligible = [e for e in events if e['voice'] == voice and any(
            w['previous_value'] is not None and w['value'] != w['previous_value']
            for w in e['configuration'])]
        for label, offsets in [('volume', (0, 1)), ('pitch', (2, 3)), ('source', (4,))]:
            ranked = []
            for event in eligible:
                changed = [w for w in event['configuration'] if w['register'] % 16 in offsets
                           and w['previous_value'] is not None and w['value'] != w['previous_value']]
                if changed:
                    ranked.append((event['keyon']['tick'] - min(w['tick'] for w in changed), event))
            for gap, event in sorted(ranked, key=lambda x: (-x[0], x[1]['packet']))[:8]:
                key = (event['packet'], voice)
                chosen.setdefault(key, dict(event=event, reasons=[]))['reasons'].append(
                    dict(selection='longest_changed_' + label, clocks=gap))
        ranked = sorted(eligible, key=lambda e: (e['keyon']['tick'] - min(
            w['tick'] for w in e['configuration']), e['packet']))
        for event in ranked[:4]:
            chosen.setdefault((event['packet'], voice), dict(event=event, reasons=[]))[
                'reasons'].append(dict(selection='shortest_setup'))
    if not chosen:
        raise ValueError('No changed pulse restarts')
    result = sorted(chosen.values(), key=lambda e: e['event']['keyon']['tick'])
    windows = []
    for item in result:
        event = item['event']
        a = min(w['tick'] for w in event['configuration']) // 32 - 16
        b = event['keyon']['tick'] // 32 + 128
        if a < 1:
            raise ValueError('Selection includes uninitialized DSP')
        item['window'] = [a, b]
        if windows and a <= windows[-1][1]:
            windows[-1][1] = max(windows[-1][1], b)
        else:
            windows.append([a, b])
    if len(windows) > 64:
        raise ValueError('Observer window capacity exceeded')
    return result, windows


def plan(capture, normal, candidate, out):
    if out.exists():
        raise ValueError('Fresh output required')
    proof, _, _ = load(capture, normal, candidate)
    if not proof['passed']:
        raise ValueError('Current game fails existing restart gate')
    selected, windows = select(proof['events'])
    paths = [Path(__file__), Path('tools/audit_postpublish_keyon.py'),
             Path('tests/test_game_prerestart.py')]
    sources = dict(proof['sources'], **{str(p): sha(p) for p in paths})
    result = dict(selected=selected, windows=windows, total_restarts=proof['restarts'],
                  candidate=str(candidate), capture=str(capture), normal=str(normal),
                  sources=sources, scope=__doc__)
    out.mkdir()
    (out/'windows.txt').write_text(''.join(f'{a} {b}\n' for a, b in windows))
    result['sources'][str(out/'windows.txt')] = sha(out/'windows.txt')
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(selected=len(selected), windows=len(windows),
                          samples=sum(b-a for a, b in windows))))


def capture(core, plan_dir, out, normal=None):
    if out.exists() or any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Fresh output and clean environment required')
    selected = bound_report(plan_dir/'report.json')
    candidate = Path(selected['candidate'])
    tree = core.parent.parent
    paths = [Path(__file__), Path('tools/capture_dsp_latency.py'),
             Path('tools/snes9x_voice_edge.inc'), Path('tools/snes9x_pulse_onset.inc'),
             Path('tools/snes9x_dsp_latency.inc'), Path('tools/benchmark_capture.py'),
             Path('tools/smoke_libretro.py'), plan_dir/'report.json', core,
             tree/'apu/bapu/dsp/SPC_DSP.cpp', tree/'apu/bapu/dsp/SPC_DSP.h',
             tree/'apu/bapu/smp/core.cpp', tree/'apu/apu.cpp']
    sources = {str(p): sha(p) for p in paths}
    env = dict(os.environ)
    trace = out.with_name(out.name+'-edges.csv')
    onset = out.with_name(out.name+'-onset.csv')
    if normal:
        if trace.exists() or onset.exists():
            raise ValueError('Fresh trace required')
        env.update(RCR_VOICE_EDGE_WINDOWS=str((plan_dir/'windows.txt').resolve()),
                   RCR_VOICE_EDGE_TRACE=str(trace.resolve()), RCR_PULSE_ONSET_TRACE=str(onset.resolve()))
        command = [sys.executable, '-m', 'tools.capture_dsp_latency', '--core', str(core),
                   '--rom', str(candidate/'native-cpu.sfc'), '--out', str(out)]
    else:
        command = [sys.executable, 'tools/benchmark_capture.py', '--system', 'snes',
                   '--core', str(core), '--rom', str(candidate/'native-cpu.sfc'),
                   '--title', 'build/reference-title-05', '--walk', 'build/reference-walk-02',
                   '--scenario', 'traversal-park-single-sweep', '--frame-images',
                   '--full-ram-telemetry', '--out', str(out)]
    subprocess.run(command, env=env, check=True)
    receipt, rows = verify_capture(out)
    if normal:
        baseline, previous = verify_capture(normal)
        equivalent(receipt, rows, baseline, previous)
        for p in (trace, onset, normal/'capture.json'):
            sources[str(p)] = sha(p)
    else:
        # Check old-core runtime compatibility separately from observer neutrality.
        baseline, previous = verify_capture(Path(selected['normal']))
        if rows != previous or receipt['audio_sha256'] != baseline['audio_sha256']:
            raise ValueError('New control differs from selected current-game route')
    if any(sha(p) != digest for p, digest in sources.items()):
        raise ValueError('Capture source changed')
    sources[str(out/'capture.json')] = sha(out/'capture.json')
    (out/'prerestart-capture.json').write_text(json.dumps(dict(sources=sources,
        observer_neutral=bool(normal), trace=str(trace) if normal else None,
        onset=str(onset) if normal else None, plan=str(plan_dir)), indent=2)+'\n')


def characterize(event, latch, groups, writes):
    voice = event['voice']
    first = min(w['tick'] for w in event['configuration'])
    last = event['keyon']['tick']
    if not last <= latch <= last+67:
        raise ValueError('Wrong hardware latch for setup')
    updates = pitch_updates(writes, voice)
    tables = ([u['low']['tick'] for u in updates], [u['high']['tick'] for u in updates],
              [u['low']['value'] for u in updates], [u['high']['value'] for u in updates])
    rows = []
    for sample, group in sorted(groups.items()):
        source = group['sources'][voice]
        if not first < source['tick'] <= latch:
            continue
        expected = sample_expectation(source['tick']+1, voice, source['previous_delay'], updates, *tables)
        if source['pitch'] != expected['expected']:
            raise ValueError('Unexplained actual pulse pitch')
        amplitude = [group['amplitudes'][voice, ch] for ch in (0, 1)]
        rows.append(dict(sample=sample, source=source, amplitudes=amplitude,
                         pitch_oracle=expected, nonzero=any(amplitude)))
    if not rows:
        raise ValueError('No setup samples')
    return dict(packet=event['packet'], voice=voice, first_config_tick=first,
                keyon_write_tick=last, hardware_latch_tick=latch, samples=rows,
                nonzero_samples=sum(r['nonzero'] for r in rows),
                split_pitch_samples=sum(r['pitch_oracle']['split_byte'] for r in rows),
                nonzero_split_samples=sum(r['nonzero'] and r['pitch_oracle']['split_byte'] for r in rows))


def audit(plan_dir, normal, observed, out):
    if out.exists():
        raise ValueError('Fresh review required')
    selection = bound_report(plan_dir/'report.json')
    binding = bound_report(observed/'prerestart-capture.json')
    control = bound_report(normal/'prerestart-capture.json')
    candidate = Path(selection['candidate'])
    proof, writes, _ = load(observed, normal, candidate)
    a, ar = verify_capture(observed)
    b, br = verify_capture(normal)
    equivalent(a, ar, b, br)
    prior = json.loads((Path(selection['capture'])/'capture.json').read_text())
    for key in ('RCR_DSP_LATENCY_TRACE', 'RCR_DSP_DAC_PCM'):
        if a['dsp_latency_observer']['traces'][key]['sha256'] != prior['dsp_latency_observer']['traces'][key]['sha256']:
            raise ValueError('Selected clock/PCM population changed')
    rate, pcm = wavfile.read(observed/'audio.wav')
    if rate != 32040 or pcm.dtype != np.int16 or pcm.ndim != 2 or pcm.shape[1] != 2:
        raise ValueError('Wrong native PCM')
    rows = parse(Path(binding['trace']), selection['windows'])
    reg = registers(writes)
    reconstructed = {s: validate_group(s, r, pcm[s], reg) for s, r in rows.items()}
    with Path(binding['onset']).open() as f:
        latches = parse_voice(list(csv.reader(f)), writes)
    matched = {(e['packet'], e['voice']): e for e in latches}
    if len(matched) != len(latches):
        raise ValueError('Ambiguous latch')
    result = [dict(characterize(e['event'], matched[e['event']['packet'], e['event']['voice']]['tick'],
                                reconstructed, writes), selection=e['reasons']) for e in selection['selected']]
    paths = [Path(__file__), Path('tests/test_game_prerestart.py'),
             Path('tools/audit_voice_edges.py'), Path('tools/audit_pulse_pitch.py'),
             Path('tools/audit_pulse_onset.py'), plan_dir/'report.json',
             observed/'prerestart-capture.json', normal/'prerestart-capture.json']
    sources = dict(selection['sources'], **binding['sources'])
    sources.update(control['sources']); sources.update(proof['sources'])
    sources.update({str(p): sha(p) for p in paths})
    report = dict(sources=sources, events=result, reconstructed_samples=len(rows),
        selected_restarts=len(result), total_restarts=selection['total_restarts'],
        nonzero_setups=sum(bool(e['nonzero_samples']) for e in result),
        split_pitch_samples=sum(e['split_pitch_samples'] for e in result),
        nonzero_split_samples=sum(e['nonzero_split_samples'] for e in result),
        full_route_observer_neutral=True, same_clock_and_pcm_as_selection=True,
        scope='Timing-selected current-game setup intervals, all-voice native DAC reconstruction. '
              'Nonzero pre-restart output is not itself a bug; split pitch is an intermediate '
              'value, not proof of an audible pop. Not hardware qualification or a whole-route '
              'absence claim. No ROM or audio changes.')
    out.mkdir()
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('sources', 'events')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name, required, optional in [('plan', ('capture', 'normal', 'candidate', 'out'), ()),
                                    ('capture', ('core', 'plan-dir', 'out'), ('normal',)),
                                    ('audit', ('plan-dir', 'normal', 'observed', 'out'), ())]:
        p = sub.add_parser(name)
        for arg in required:
            p.add_argument('--'+arg, type=Path, required=True)
        for arg in optional:
            p.add_argument('--'+arg, type=Path)
    args = vars(parser.parse_args())
    globals()[args.pop('command')](**args)
