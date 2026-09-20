"""Separate repeated camera commands from delayed display in original NES traces.

Diagnostic only. A matching counterexample in NES does not clear an unmatched
physical SNES hold, nor establish why the game requested an unchanged camera.
"""
import argparse
import csv
import json
from pathlib import Path

from tools.audit_display_cadence import measure
from tools.audit_main_display_latency import bound_report
from tools.audit_nes_main_phase import pair
from tools.benchmark_report import sha, verify_capture


def classify(phases, iterations):
    starts = [r['start']['frame'] for r in iterations]
    commits = [r['commit']['frame'] for r in iterations]
    if starts != sorted(set(starts)) or commits != sorted(set(commits)):
        raise ValueError('Main iterations must be strictly ordered')
    results = []
    for name, phase in phases.items():
        if measure(phase['series']) != phase:
            raise ValueError('Changed camera derivation')
        displayed = {r['frame']: r['camera'] for r in phase['series']}
        for hold in phase['intervals']:
            if not abs(hold['start_delta']) == 1 or hold['start_delta'] != hold['end_delta']:
                continue
            first, last = hold['start'], hold['end']
            # Explicit hypothesis: stores appear in the NEXT rendered frame.
            # Include both endpoint-producing stores, not just unchanged ones.
            work = [r for r in iterations if first-1 <= r['commit']['frame'] <= last-1]
            covered = bool(work and work[0]['commit']['frame'] == first-1 and
                           work[-1]['commit']['frame'] == last-1)
            regular = covered and len(work) >= 2 and all(
                b['start']['frame']-a['start']['frame'] == 2 and
                b['commit']['frame']-a['commit']['frame'] == 2
                for a, b in zip(work, work[1:])) and all(
                    r['commit']['frame']-r['start']['frame'] == 1 for r in work)
            visible = covered and all(
                displayed.get(f) == current['commit']['camera']
                for i, current in enumerate(work)
                for f in range(current['commit']['frame']+1,
                    work[i+1]['commit']['frame']+1 if i+1 < len(work) else last+1))
            repeats = sum(a['commit']['camera'] == b['commit']['camera']
                          for a, b in zip(work, work[1:]))
            supported = bool(regular and visible and repeats)
            results.append(dict(phase=name, hold=hold, iterations=work,
                endpoint_stores_covered=covered, two_frame_main_cadence=regular,
                all_stores_visible_next_frame=visible, repeated_camera_commits=repeats,
                classification='repeated_command_with_regular_main' if supported else
                    'outside_main_window' if not covered else 'not_explained_by_repeated_command'))
    return results


def audit(main, cadence, normal, run, out):
    execution = bound_report(main)
    rendering = bound_report(cadence)['runs'][run]
    receipt, rows = verify_capture(normal)
    control = str(normal/'capture.json')
    if (execution['sources'].get(control) != sha(normal/'capture.json') or
            rendering['sources'].get(control) != sha(normal/'capture.json') or
            receipt['system'] != 'nes' or not receipt['capture_complete']):
        raise ValueError('Need common complete original NES control')
    # Recompute the main pairing from its authenticated raw events.
    traces = [Path(p) for p in execution['sources'] if p.endswith('.csv')]
    if len(traces) != 1:
        raise ValueError('Need exactly one raw main event trace')
    with traces[0].open() as stream:
        iterations, censored = pair(list(csv.reader(stream)))
    if iterations != execution['intervals'] or censored != execution['censored']:
        raise ValueError('Changed main derivation')
    # JSON object keys in histograms are strings; rederive them before compare.
    phases = {}
    for name, phase in rendering['phases'].items():
        derived = measure(phase['series'])
        if json.loads(json.dumps(derived)) != phase:
            raise ValueError('Changed camera derivation')
        phases[name] = derived
    events = classify(phases, iterations)
    examples = [e for e in events if e['hold']['frames'] == 4 and
                e['classification'] == 'repeated_command_with_regular_main']
    if not examples:
        raise ValueError('No measured four-frame repeated-command counterexample')
    contexts = []
    for e in examples:
        context = []
        for row in rows[e['hold']['start']-5:e['hold']['end']+2]:
            ram = bytes.fromhex(row['game_ram_hex'])
            context.append(dict(frame=row['frame'], player_x=ram[0x388]+256*ram[0x390],
                player_y=ram[0x398], committed_camera=ram[0xf6]+256*(ram[0x3d]&1),
                working_camera=ram[0xdc]+256*ram[0xdd], main_complete=ram[0x10b],
                input_delivered=row['input_delivered']))
        contexts.append(context)
    paths = [Path(__file__), Path('tools/audit_display_cadence.py'),
             Path('tools/audit_main_display_latency.py'), Path('tools/audit_nes_main_phase.py'),
             Path('tools/benchmark_report.py'), main, cadence, normal/'capture.json']
    report = dict(events=events, four_frame_counterexamples=examples, contexts=contexts,
        physical_holds_explained=False, speed_verified=False, release_ready=False,
        sources={str(p):sha(p) for p in paths},
        scope='Original NES one-pixel equal-signed endpoint holds; all retained, including '
              'outside the exact-PC trace window. Next-frame publication is an explicit '
              'checked hypothesis, not assumed globally. A repeated camera command is '
              'not a missed main iteration. No knockback/collision cause inferred; '
              'unmatched Rival footage remains unresolved.')
    out.mkdir(parents=True, exist_ok=False)
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(holds=len(events), counterexamples=examples), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('main', 'cadence', 'normal', 'out'):
        parser.add_argument('--'+name, required=True, type=Path)
    parser.add_argument('--run', required=True)
    audit(**vars(parser.parse_args()))
