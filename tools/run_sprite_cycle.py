"""One focused sprite-fix cycle: cached parent, fresh trial, symptom gates, web evidence.

This deliberately does NOT run broad qualification or promote a cartridge.
The prefix boots normally and ends after right_04; no save-state/RAM mutation.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

from tools.audit_main_display_latency import bound_report
from tools.audit_sprite_publication import load
from tools.benchmark_report import sha
from tools.capture_sprite_prefix import installed_prefix
from tools.frame_audit import verify_frame


def gates(before, after, original_rows, trial_rows):
    same_sources = [(g['source_frame'], g['source_sha256']) for g in before['generations']] == [
        (g['source_frame'], g['source_sha256']) for g in after['generations']]
    known = [g for g in after['generations'] if not g['left_censored']]
    return dict(structural=before['structural_passed'] and after['structural_passed'],
        same_source_generations=same_sources,
        every_known_generation_displayed_next_frame=bool(known) and all(
            g['source_to_first_render_frames'] == 1 for g in known),
        original_game_counter_unchanged=[r['probe_052b'] for r in original_rows] == [r['probe_052b'] for r in trial_rows],
        logical_camera_unchanged=[r['native']['logical_camera_x'] for r in original_rows] == [
            r['native']['logical_camera_x'] for r in trial_rows],
        input_delivery_unchanged=[(r['input_requested'], r['input_delivered']) for r in original_rows] == [
            (r['input_requested'], r['input_delivered']) for r in trial_rows],
        no_adapter_faults=not any(r['fault'] for r in original_rows+trial_rows))


def run(candidate, out, parent=Path('build/tail-startup-pitch-game-3219'),
        parent_observed=Path('build/sprite-prefix-parent-observed-3255'),
        trial_normal=None, trial_observed=None):
    if out.exists(): raise ValueError('Fresh cycle directory required')
    started = time.monotonic(); timing = {}
    # Revalidate the immutable cached parent including observer/control equality;
    # a changed source, core, input policy or capture is not a cache hit.
    with installed_prefix(): baseline = load(parent_observed, parent)
    timing['verify_cached_parent_seconds'] = time.monotonic()-started
    if (baseline[0]['first'], baseline[0]['last'], baseline[0].get('last_phase')) != (1978, 2020, 'right_04'):
        raise ValueError('Wrong cached prefix/window')
    reused = trial_normal is not None or trial_observed is not None
    if reused and (trial_normal is None or trial_observed is None): raise ValueError('Need both trial captures')
    out.mkdir()
    if not reused:
        trial_normal = out/'normal'; trial_observed = out/'observed'
        for target, extra in ((trial_normal, []), (trial_observed, ['--observed', '--control', str(trial_normal)])):
            tick = time.monotonic()
            with (out/(target.name+'.log')).open('w') as log:
                subprocess.run([sys.executable, '-m', 'tools.capture_sprite_prefix', '--candidate', str(candidate),
                    '--out', str(target)]+extra, check=True, stdout=log, stderr=subprocess.STDOUT)
            timing[target.name+'_seconds'] = time.monotonic()-tick
    with installed_prefix(): trial = load(trial_observed, candidate)
    if trial[0]['reference'] != str(trial_normal): raise ValueError('Wrong trial control')
    if (trial[0]['first'], trial[0]['last'], trial[0].get('last_phase')) != (1978, 2020, 'right_04'):
        raise ValueError('Wrong trial window')
    checks = gates(baseline[2], trial[2], baseline[1], trial[1])
    sources = dict(baseline[0]['sources'], **trial[0]['sources'])
    for root in (parent_observed, trial_observed):
        sources[str(root/'sprite-events-capture.json')] = sha(root/'sprite-events-capture.json')
    for p in (Path(__file__), Path('tests/test_sprite_cycle.py'), Path('tools/audit_sprite_publication.py'),
              Path('tools/capture_sprite_prefix.py'), Path('tools/frame_audit.py')):
        sources[str(p)] = sha(p)
    records = {}
    for name, data in (('parent', baseline), ('trial', trial)):
        events = [r['frame'] for a, r in zip(data[1][1500:], data[1][1501:]) if a['probe_052b'] != r['probe_052b']]
        records[name] = {k: data[2][k] for k in ('known_source_generations', 'source_to_first_render_histogram',
            'not_rendered_in_window', 'generations', 'failures')}
        records[name]['counter_interval_histogram_after_frame_1500'] = dict(Counter(b-a for a, b in zip(events, events[1:])))
    changed = [a['frame'] for a, b in zip(baseline[2]['renders'], trial[2]['renders']) if a['oam_sha256'] != b['oam_sha256']]
    cards = []
    # All changed frame numbers retained; first six form a compact review.
    for frame in changed[:6]:
        cards.append(f'<h3>Frame {frame}</h3><div class="pair">')
        for name, root, data in (('parent', parent_observed, baseline), ('trial', trial_observed, trial)):
            source = verify_frame(root, data[1][frame-1]); sources[str(source)] = sha(source)
            filename = f'{frame}-{name}.png'; shutil.copyfile(source, out/filename)
            cards.append(f'<figure><img src="{filename}"><figcaption>{name}</figcaption></figure>')
        cards.append('</div>')
    timing['total_seconds'] = time.monotonic()-started
    report = dict(candidate=str(candidate), rom_sha256=sha(candidate/'native-cpu.sfc'), gates=checks,
        passed=all(checks.values()), prefix_frames=len(trial[1]), observed_window=[1978, 2020],
        parent=records['parent'], trial=records['trial'], timing=timing, reused_trial=reused,
        displayed_oam_changed_frames=changed, sources=sources, release_ready=False, hardware_tested=False,
        scope=__doc__+' Source frames and byte hashes must match exactly across arms. '
            'Original game counter is a prefix regression check, not full-game/NES speed certification. '
            'Audio perceptual fidelity, menus, transitions and scanline safety need separate broad gates.')
    body = '<!doctype html><meta charset="utf-8"><title>Focused sprite cycle</title>'
    body += '<style>body{background:#111a26;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}a{color:#8df}.pair{display:flex}figure{margin:8px;flex:1}img{width:100%;image-rendering:pixelated}</style>'
    body += f'<h1>Focused sprite-fix cycle: {"PASS" if report["passed"] else "FAIL"}</h1>'
    body += f'<p>{report["prefix_frames"]:,} boot-driven frames; sprite window 1978–2020. '
    body += 'Same-core observer/control checked independently for both cartridges. No hardware deployment.</p>'
    for name, r in records.items():
        body += f'<p>{name}: first-display delay {r["source_to_first_render_histogram"]}; '
        body += f'{len(r["not_rendered_in_window"])} of {r["known_source_generations"]} known generations not displayed in the window.</p>'
    body += '<ul>'+''.join(f'<li>{k}: {v}</li>' for k, v in checks.items())+'</ul>'
    body += '<p>First six changed OAM frames shown; all changed indices and source generations are retained in '
    body += '<a href="report.json">the bound report</a>. This focused result does not certify audio, scrolling, or full-game speed.</p>'
    body += ''.join(cards)
    (out/'index.html').write_text(body)
    if any(sha(Path(p)) != h for p, h in sources.items()): raise ValueError('Changed source during cycle')
    report['artifacts'] = {p.name: sha(p) for p in out.iterdir() if p.is_file()}
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'], gates=checks, seconds=timing['total_seconds'], reused_trial=reused)))
    return report['passed']


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'out'): p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--parent', type=Path, default=Path('build/tail-startup-pitch-game-3219'))
    p.add_argument('--parent-observed', type=Path, default=Path('build/sprite-prefix-parent-observed-3255'))
    for name in ('trial-normal', 'trial-observed'): p.add_argument('--'+name, type=Path)
    sys.exit(0 if run(**vars(p.parse_args())) else 1)
