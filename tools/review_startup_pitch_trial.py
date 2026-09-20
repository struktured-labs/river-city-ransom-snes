"""Check actual restart-pitch writes against the DSP startup window."""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from tools.audit_main_display_latency import bound_report
from tools.audit_recorded_transients import waveform_svg
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.review_native_transient_stems import same_core_load


def compare_timeline(first, second, first_samples, second_samples):
    if len(first) != len(second) or not first:
        raise ValueError('Incomplete cross-arm source timeline')
    differences = []
    for a, b in zip(first, second):
        fixed = (set(a) | set(b)) - {'start_sample', 'end_sample'}
        if any(a.get(k) != b.get(k) for k in fixed):
            raise ValueError('Cross-arm source input or player cadence changed')
        if a != b:
            differences.append(dict(source_frame=a['source_frame'],
                baseline=[a['start_sample'], a['end_sample']],
                trial=[b['start_sample'], b['end_sample']]))
    return dict(exact_callback_timeline_equal=not differences,
                sample_count_equal=first_samples == second_samples,
                baseline_samples=first_samples, trial_samples=second_samples,
                callback_differences=differences,
                scope='Strict differences retained; no trimming, retiming, or waiver of game timing qualification.')


def startup_window(event, writes, ready):
    voice = event['voice']; packet = event['packet']; keyon = event['keyon_write']['tick']
    pitch = [w for w in writes if w['packet'] == packet and w['register'] in (16*voice+2, 16*voice+3)
             and w['tick'] < ready[packet]['tick']]
    if len(pitch) != 2 or [w['register'] % 16 for w in pitch] != [2, 3]:
        raise ValueError('Need exactly one complete pitch pair for this restart')
    # At index1 V3c has cleared the envelope. The first advancing oscillator
    # pitch is read before index6 V4, at distinct per-voice low/high phases.
    silent = event['tick']+32
    first_low = event['samples'][6]['tick']-(10 if voice == 0 else 2)
    first_high = first_low+1
    return dict(packet=packet, voice=voice, kon_tick=keyon, latch_tick=event['tick'],
        silent_from=silent, first_oscillator_low_read=first_low, pitch_writes=pitch,
        low_after_silence=pitch[0]['tick'] > silent,
        high_after_silence=pitch[1]['tick'] > silent,
        low_before_first_read=pitch[0]['tick'] < first_low,
        high_before_first_read=pitch[1]['tick'] < first_high,
        first_pitch_matches=event['first_pitch_matches'],
        passed=(silent < pitch[0]['tick'] < first_low and
                silent < pitch[1]['tick'] < first_high and event['first_pitch_matches']))


def mutant(fixture, delay, out):
    if out.exists() or delay not in (1, 64):
        raise ValueError('Fresh output and fixed early/late control required')
    spec = bound_report(fixture/'manifest.json')
    engine = bytearray((fixture/'engine.bin').read_bytes())
    pattern = bytes.fromhex('cd101dd0fd')
    if engine.count(pattern) != 1:
        raise ValueError('Missing unique startup wait')
    at = engine.index(pattern)+1
    engine[at] = delay
    image = bytearray((fixture/'player.sfc').read_bytes())
    if image[0x120000:0x120000+len(engine)] != (fixture/'engine.bin').read_bytes():
        raise ValueError('Wrong embedded engine')
    image[0x120000+at] = delay
    checksum(image)
    out.mkdir()
    for name, value in [('engine.bin', engine), ('player.sfc', image), ('stream.bin', (fixture/'stream.bin').read_bytes())]:
        (out/name).write_bytes(value)
    paths = [Path(__file__), Path('tests/test_startup_pitch_window.py'),
             Path('tools/build_inline_pitch_trial.py'), fixture/'manifest.json', fixture/'engine.bin',
             fixture/'player.sfc', fixture/'stream.bin']
    paths += [out/n for n in ('engine.bin', 'player.sfc', 'stream.bin')]
    spec.update(mutation=f'startup-delay-negative-{delay}', negative_delay=delay,
        rom_sha256=sha(out/'player.sfc'), spc_sha256=sha(out/'engine.bin'),
        sources={str(p): sha(p) for p in paths})
    (out/'manifest.json').write_text(json.dumps(spec, indent=2)+'\n')


def review(specification, out):
    if out.exists():
        raise ValueError('Fresh review required')
    spec = json.loads(specification.read_text())
    paths = [Path(__file__), Path('tests/test_startup_pitch_window.py'), specification,
             Path('tools/audit_pulse_onset.py'), Path('tools/review_native_transient_stems.py'),
             Path('tools/audit_recorded_transients.py')]
    sources = {str(p): sha(p) for p in paths}
    results, loaded = {}, {}
    for name, config in spec['captures'].items():
        fixture, normal, observed = (Path(config[k]) for k in ('fixture', 'normal', 'observed'))
        onset, _, writes, ready = same_core_load(observed, normal, fixture)
        windows = [startup_window(e, writes, ready) for e in onset['events']]
        results[name] = dict(restarts=onset['restarts'], eligible=onset['eligible'],
            wrong_first_pitch=onset['wrong_first_pitch'], stale_nonzero_onsets=onset['stale_nonzero_onsets'],
            failed_windows=sum(not w['passed'] for w in windows), windows=windows,
            kon_phases=sorted({e['keyon_write']['tick'] % 64 for e in onset['events']}),
            low_minus_kon=sorted({w['pitch_writes'][0]['tick']-w['kon_tick'] for w in windows}),
            high_minus_kon=sorted({w['pitch_writes'][1]['tick']-w['kon_tick'] for w in windows}))
        for p in (fixture/'manifest.json', normal/'report.json', observed/'onset-observer.json'):
            binding = bound_report(p)
            sources.update(binding.get('sources', {})); sources[str(p)] = sha(p)
        rate, pcm = wavfile.read(normal/'audio.wav')
        if rate != 32040 or pcm.dtype != np.int16 or pcm.ndim != 2 or pcm.shape[1] != 2:
            raise ValueError('Wrong native audio')
        loaded[name] = dict(fixture=fixture, normal=normal, observed=observed, onset=onset,
                            pcm=pcm, rate=rate, timeline=json.loads((normal/'timeline.json').read_text()))
    # Diagnostic baseline is expected to write before KON, not inside startup.
    for name in ('held_trial', 'changing_trial'):
        if results[name]['failed_windows'] or results[name]['wrong_first_pitch']:
            raise ValueError('Trial missed a silent startup window')
    for name in ('early_negative', 'late_negative'):
        if not results[name]['failed_windows']:
            raise ValueError('Executed startup-delay negative survived')
    qualification = bound_report(Path(spec['state_report']))
    if not qualification['passed']:
        raise ValueError('State/timer qualification failed')
    sources.update(qualification['sources'])
    sources[spec['state_report']] = sha(spec['state_report'])
    comparisons = {}
    for first, second in [('held_baseline', 'held_trial'), ('changing_baseline', 'changing_trial')]:
        a, b = loaded[first], loaded[second]
        if sha(a['fixture']/'stream.bin') != sha(b['fixture']/'stream.bin'):
            raise ValueError('Different packet stream')
        comparisons[first] = compare_timeline(a['timeline'], b['timeline'], len(a['pcm']), len(b['pcm']))
    out.mkdir()
    cards, clips = [], []
    # Fixed changed-note case: both voices, duty0, first large period change.
    config = json.loads((loaded['changing_baseline']['fixture']/'manifest.json').read_text())
    case = next(c for c in config['cases'] if c['mask'] == 3 and c['duty'] == 0)
    for name in ('changing_baseline', 'changing_trial', 'early_negative', 'late_negative'):
        arm = loaded[name]
        row = next(r for r in arm['timeline'] if r['source_frame'] == case['changed_frame'])
        first, last = max(0, row['start_sample']-8000), min(len(arm['pcm']), row['start_sample']+8000)
        clip = arm['pcm'][first:last]
        wavfile.write(out/(name+'.wav'), arm['rate'], clip)
        rate, decoded = wavfile.read(out/(name+'.wav'))
        if rate != arm['rate'] or not np.array_equal(decoded, clip):
            raise ValueError('Changed native clip')
        clips.append(dict(name=name, source=str(arm['normal']/'audio.wav'), first=first, last=last))
        cards.append(f'<section><h2>{name}</h2>'+waveform_svg(clip)+
                     f'<audio controls preload="none" src="{name}.wav"></audio></section>')
    table = ''.join(f'<tr><td>{name}</td><td>{r["restarts"]}</td><td>{r["failed_windows"]}</td>'
                    f'<td>{r["wrong_first_pitch"]}</td><td>{len(r["kon_phases"])}</td></tr>' for name, r in results.items())
    html = '<!doctype html><meta charset="utf-8"><title>Restart pitch staging trial</title>'
    html += '<style>body{background:#111a26;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}'
    html += 'a{color:#7df}th,td{padding:10px;border-bottom:1px solid #456}.cards{display:grid;grid-template-columns:1fr 1fr;gap:20px}'
    html += 'section{background:#243044;padding:18px}audio{width:100%}</style>'
    html += '<h1>Offline restart-pitch staging trial</h1><p>Actual SPC implementation: defer restarting voices’ '
    html += 'pitch until DSP startup silence. Ordinary non-restart pitch updates retain their five-clock write gap.</p>'
    html += '<p>No production game, hardware, graphics, or controls changed. Native synthetic-player audio below; '
    html += 'not gameplay or a physical pop-fix claim. Baseline/trial use identical extended upload lengths.</p>'
    html += '<table><tr><th>Arm</th><th>Restarts</th><th>Outside silent window</th><th>Wrong first pitch</th><th>KON phases /64</th></tr>'+table+'</table>'
    html += '<p>Baseline writes before restart by design. Early/late arms are deliberately incorrect executed '
    html += 'delay variants; their failures demonstrate timing sensitivity. Phase coverage is measured, not presumed exhaustive.</p>'
    html += f'<p>State cases: {qualification["cases"]:,}; actual DSP/MMIO exceptions and service cost are retained '
    html += 'in the source report. Added code/upload size, service cost, original-NES fidelity, full-game '
    html += 'timing, and ordinary non-restart split-pitch samples remain release blockers.</p>'
    html += '<h2>Retained strict timing differences</h2>'
    for name, comparison in comparisons.items():
        html += f'<p>{name}: {len(comparison["callback_differences"])} callback-boundary differences; '
        html += f'{comparison["baseline_samples"]:,} baseline / {comparison["trial_samples"]:,} trial samples. '
        html += 'Not an exact cross-arm callback timing pass.</p>'
    html += '<div class="cards">'+''.join(cards)+'</div><p><a href="report.json">Full measurements and bindings</a></p>'
    (out/'index.html').write_text(html)
    result = dict(results=results, clips=clips, cross_arm_timing=comparisons, state_report=spec['state_report'],
        sources=sources, artifacts={p.name: sha(p) for p in out.iterdir()},
        executed_negatives_rejected=True, game_changed=False, release_ready=False,
        scope='Executed silent-startup timing, final register state and transport checks. '
              'Not a claim of original-NES waveform improvement or physical pop elimination.')
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({n: {k: v for k, v in r.items() if k not in ('windows', 'kon_phases')}
                      for n, r in results.items()}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    m = sub.add_parser('mutant')
    for name in ('fixture', 'out'):
        m.add_argument('--'+name, type=Path, required=True)
    m.add_argument('--delay', type=int, required=True)
    r = sub.add_parser('review')
    for name in ('specification', 'out'):
        r.add_argument('--'+name, type=Path, required=True)
    args = vars(p.parse_args()); globals()[args.pop('command')](**args)
