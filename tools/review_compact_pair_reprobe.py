"""Combine same-state transition proof with independent route qualification."""
import argparse
import html
import json
from pathlib import Path
import shutil

import numpy as np

from tools.audit_main_display_latency import bound_report
from tools.audit_scroll_publication import BACKGROUND_REGION, rgb555
from tools.benchmark_report import sha, verify_capture
from tools.review_combat_checkpoints import load, transition


def with_initial(root, report, rows):
    raw = (root/'initial.ram').read_bytes()
    if len(raw) != 131072 or not rows or rows[0]['frame'] != report['restored_frame']+1:
        raise ValueError('Missing authenticated replay boundary')
    return [dict(frame=report['restored_frame'], game_ram_hex=raw[:2048].hex(),
                 native_ram_hex=raw[0x1C00:0x2000].hex())]+rows


def build(out):
    if out.exists():
        raise ValueError('Fresh output required')
    sources, reports = {}, {}
    specs = dict(oracle='compact-pair-oracle-2247', school='compact-pair-school-audit-2248',
        combat='compact-pair-combat-review-2249', renderer='compact-pair-render-audit-2261',
        cadence='compact-pair-cadence-2262', audio='compact-pair-audio-2263')
    for label, directory in specs.items():
        root = Path('build')/directory
        reports[label] = bound_report(root/'report.json')
        sources.update(reports[label]['sources'])
        sources[str(root/'report.json')] = sha(root/'report.json')
        for name, digest in reports[label].get('artifacts', {}).items():
            if sha(root/name) != digest:
                raise ValueError('Changed qualification artifact')
    for side in ('baseline', 'candidate'):
        for name, digest in reports['audio'][side]['sources'].items():
            if sha(Path(name)) != digest:
                raise ValueError('Changed DSP source')
            sources[name] = digest
    forward_path = Path('build/compact-pair-entry-2250/report.json')
    forward = json.loads(forward_path.read_text())
    for side, root in (('nes', Path('build/park-single-nes-331')),
                       ('snes', Path('build/compact-pair-route-2246'))):
        receipt, _ = verify_capture(root)
        if forward['sources'][side] != dict(rom_sha256=receipt['rom_sha256'], capture_sha256=sha(root/'capture.json')):
            raise ValueError('Different forward-entry capture')
        sources[str(root/'capture.json')] = sha(root/'capture.json')
    if forward['audit_sha256'] != sha(Path('tools/audit_room_entry.py')):
        raise ValueError('Different forward-entry auditor')
    sources[str(forward_path)] = sha(forward_path)
    for observed, normal in (('compact-pair-render-2256', 'compact-pair-route-2246'),
            ('compact-pair-main-2260', 'compact-pair-main-normal-2259'),
            ('compact-pair-dsp-2257', 'compact-pair-dsp-normal-2258')):
        a, b = (verify_capture(Path('build')/p)[0] for p in (observed, normal))
        if a['core_sha256'] != b['core_sha256']:
            raise ValueError('Observer control core differs')
    out.mkdir(parents=True)
    comparisons, cards = {}, []
    x0, y0, x1, y1 = BACKGROUND_REGION
    for location, control, trial in (
            ('school', 'compact-pair-school-control-2253', 'compact-pair-school-resume-2255'),
            ('alley', 'compact-pair-alley-control-2252', 'compact-pair-alley-resume-2254')):
        control_root, trial_root = (Path('build')/p for p in (control, trial))
        baseline, plain = load(control_root)
        tested, changed = load(trial_root)
        if (not baseline['passed'] or tested['trial']['variant'] != 'compact-pair'
                or Path(tested['trial']['resume_control']) != control_root
                or baseline['initial_registers'] != tested['initial_registers']
                or (control_root/'initial.ram').read_bytes() != (trial_root/'initial.ram').read_bytes()
                or [r['input_requested'] for r in plain] != [r['input_requested'] for r in changed]):
            raise ValueError('Different initial state or input')
        entries, pictures, reference = [], {}, None
        for label, root, report, rows in (('parent', control_root, baseline, plain),
                                          ('trial', trial_root, tested, changed)):
            rows = with_initial(root, report, rows)
            measured = transition(rows)
            index = measured['enable_index']
            pixels = [rgb555(root/r['frame_image'])[y0:y1, x0:x1] for r in rows[index:index+40]]
            if reference is None:
                reference = pixels
            first = next((i for i, p in enumerate(pixels) if np.any(p)), None)
            measured.update(variant=label, source=str(root), first_nonblack_offset=first,
                change_to_visible=None if first is None else measured['enable_frame']+first-measured['change_frame'],
                off_to_visible=None if first is None else measured['enable_frame']+first-measured['off_frame'],
                fixed_offset_mismatch_pixels=[int(np.any(a != b, axis=2).sum()) for a, b in zip(reference, pixels)],
                initial_checks=report['initial_checks'])
            entries.append(measured)
            pictures[label] = {}
            for offset in (0, 7, 8, 14, 18, 39):
                row = rows[index+offset]
                source = root/row['frame_image']
                if sha(source) != row['frame_image_sha256']:
                    raise ValueError('Changed checkpoint screenshot')
                name = f'{location}-{label}-{offset}.png'
                shutil.copyfile(source, out/name)
                pictures[label][offset] = name
                sources[str(source)] = sha(source)
            shutil.copyfile(root/'audio.wav', out/f'{location}-{label}.wav')
            sources.update(report['sources'])
            for name in ('report.json', 'initial.ram', 'timeline.json', 'audio.wav'):
                sources[str(root/name)] = sha(root/name)
        comparisons[location] = entries
        cards.append(f'<h2>{location}: identical starting state and inputs</h2><pre>'+html.escape(json.dumps([
            {k: e[k] for k in ('variant','change_to_visible','off_to_visible','first_nonblack_offset',
                               'off_cadence_completion_intervals')} for e in entries], indent=2))+'</pre>')
        for offset in (0, 7, 8, 14, 18, 39):
            cards.append(f'<h3>Enable +{offset}</h3><div class="grid">'+''.join(
                f'<figure><img src="{pictures[label][offset]}"><figcaption>{label}</figcaption></figure>'
                for label in ('parent', 'trial'))+'</div>')
        for label in ('parent', 'trial'):
            cards.append(f'<p>{location}/{label}: entire native 180-frame replay, no processing</p>'
                         f'<audio controls preload="none" src="{location}-{label}.wav"></audio>')
    for name in (__file__, 'tools/review_combat_checkpoints.py', 'tools/audit_scroll_publication.py',
                 'tools/audit_main_display_latency.py', 'tools/audit_room_entry.py',
                 'tools/benchmark_report.py', 'tests/test_compact_pair_reprobe.py'):
        sources[str(name)] = sha(Path(name))
    if any(sha(Path(name)) != digest for name, digest in sources.items()):
        raise ValueError('Sources changed during review')
    result = dict(comparisons=comparisons, same_start_state_verified=True,
        oracle=dict(cases=len(reports['oracle']['cases']), mutants=reports['oracle']['mutants']),
        school_gates=reports['school']['gates'], forward_gates=forward['gates'],
        renderer={k: v for k, v in reports['renderer'].items() if k not in ('sources', 'images')},
        cadence=dict(passed=reports['cadence']['passed'], holds=reports['cadence']['holds'],
            loops=sum(len(r['iterations']) for r in reports['cadence']['main']['rooms'].values())),
        combat=dict(passed=reports['combat']['passed'], outliers=reports['combat']['outliers'],
            policies={p: dict(passed=r['passed'], loops=len(r['iterations']))
                      for p, r in reports['combat']['policies'].items()}),
        audio={k: v for k, v in reports['audio']['candidate'].items() if k not in ('events', 'sources')},
        sources=sources, release_ready=False, deployed=False, physical_audio_verified=False,
        scope='Same-state replay fixes the school first-update completion interval3→2 and first scenery8→7. '
        'The23-frame load remains. Full independent route passes scoped fade/renderer/cadence/audio checks '
        'only when shown below; combat still fails at the15-frame alley load. Its changed independent '
        'encounter no longer returns to school and is NOT evidence of that fix. No physical audio, '
        'worst-case producer deadline or full-game original-speed certification. All long holds retained.')
    page = '<!doctype html><meta charset="utf-8"><title>Compact paired rows: same-state improvement</title><style>body{font:17px system-ui;background:#101820;color:#eef;max-width:1150px;margin:30px auto}a{color:#8df}.grid{display:flex}img{width:384px;image-rendering:pixelated}pre{white-space:pre-wrap}audio{width:100%}</style>'
    page += '<h1>Same-state school return: missed frame removed</h1><p>'+html.escape(result['scope'])+'</p><p><a href="report.json">All measurements and source bindings</a> · <a href="manifest.json">Artifact hashes</a> · <a href="../compact-pair-combat-review-2249/">Retained combat failure and native audio</a></p>'
    page += '<h2>Independent qualification</h2><pre>'+html.escape(json.dumps({k: result[k] for k in (
        'oracle','school_gates','forward_gates','renderer','cadence','audio')}, indent=2))+'</pre>'+''.join(cards)
    (out/'index.html').write_text(page)
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    (out/'manifest.json').write_text(json.dumps(dict(sources=sources,
        artifacts={p.name: sha(p) for p in out.iterdir() if p.is_file()}, release_ready=False), indent=2)+'\n')
    print(json.dumps(dict(out=str(out), sources=len(sources), release_ready=False)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    build(**vars(p.parse_args()))
