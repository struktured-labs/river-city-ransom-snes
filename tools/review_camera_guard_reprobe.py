"""Publish deadline-reprobe results, including retained combat and camera holds."""
import argparse
import html
import json
from pathlib import Path
import shutil

from tools.audit_display_cadence import observe
from tools.audit_main_display_latency import bound_report
from tools.audit_uniform_holds import summarize
from tools.benchmark_report import sha, verify_capture


def build(out):
    if out.exists():
        raise ValueError('Fresh output required')
    sources = {}
    specs = dict(oracle='camera-guard-oracle-2229',
                 spans='camera-guard-spans-audit-2235',
                 school='camera-guard-school-audit-2226',
                 renderer='camera-guard-render-audit-2228',
                 combat='camera-guard-combat-review-2232',
                 audio='camera-guard-audio-2236')
    reports = {}
    for label, directory in specs.items():
        root = Path('build')/directory
        r = bound_report(root/'report.json')
        reports[label] = r
        sources.update(r['sources'])
        sources[str(root/'report.json')] = sha(root/'report.json')
        for name, digest in r.get('artifacts', {}).items():
            if sha(root/name) != digest:
                raise ValueError('Changed artifact: '+name)
        if label == 'audio':
            for side in ('baseline', 'candidate'):
                for path, digest in r[side]['sources'].items():
                    if sha(Path(path)) != digest:
                        raise ValueError('Changed DSP source')
                    sources[path] = digest
    combat_manifest = Path('build')/specs['combat']/'manifest.json'
    for name, digest in json.loads(combat_manifest.read_text())['artifacts'].items():
        if sha(combat_manifest.parent/name) != digest:
            raise ValueError('Changed combat artifact')
    sources[str(combat_manifest)] = sha(combat_manifest)
    normal, observed = (Path('build')/p for p in ('camera-guard-route-2223', 'camera-guard-render-2225'))
    if verify_capture(normal)[0]['core_sha256'] != verify_capture(observed)[0]['core_sha256']:
        raise ValueError('Renderer control core differs')
    cadence = observe(observed, normal, 'snes')
    sources.update(cadence['sources'])
    holds = {phase: summarize(values) for phase, values in cadence['phases'].items()}
    forward_path = Path('build/camera-guard-entry-2227/report.json')
    forward = json.loads(forward_path.read_text())
    for side, root in (('nes', Path('build/park-single-nes-331')), ('snes', normal)):
        receipt, _ = verify_capture(root)
        if forward['sources'][side] != dict(rom_sha256=receipt['rom_sha256'], capture_sha256=sha(root/'capture.json')):
            raise ValueError('Forward entry binding differs')
        sources[str(root/'capture.json')] = sha(root/'capture.json')
    if forward['audit_sha256'] != sha(Path('tools/audit_room_entry.py')):
        raise ValueError('Forward entry auditor differs')
    sources[str(forward_path)] = sha(forward_path)
    rom = Path('build/camera-guard-trial-2221/native-cpu.sfc')
    if sha(rom) != reports['combat']['rom_sha256']:
        raise ValueError('Different combat cartridge')
    spans = reports['spans']
    result = dict(rom_sha256=sha(rom), release_ready=False, deployed=False,
        production_worst_case_bound_proven=False, pop_free_verified=False,
        oracle=dict(passed=reports['oracle']['passed'], cases=len(reports['oracle']['cases']),
                    mutants=reports['oracle']['mutants']),
        scheduling={k: spans[k] for k in ('passed', 'gates', 'stable_frames', 'outcomes',
                     'admitted_max_elapsed_clocks', 'producer_calls_on_fallback_ticks')},
        school_gates=reports['school']['gates'], forward_gates=forward['gates'],
        renderer={k: reports['renderer'][k] for k in ('passed', 'eligible_frames', 'checked_held_frames',
                     'coverage_failures', 'splits', 'stale_camera_failures')},
        combat=dict(passed=reports['combat']['passed'],
            policies={p: dict(passed=r['passed'], iterations=len(r['iterations']))
                      for p, r in reports['combat']['policies'].items()},
            outliers=reports['combat']['outliers']),
        holds=holds, cadence=cadence,
        audio={k: v for k, v in reports['audio']['candidate'].items() if k not in ('events', 'sources')},
        sources=sources,
        scope='Offline historical line194 guard on the faster current parent. Full neutral sustained-combat '
        'trace accounts for actual producers and stable-frame NMI entries. Measured maxima are not a '
        'worst-case deadline proof. Running/jumping failures and seven long camera holds remain. '
        'Native audio packet/order tests do not establish pop-free physical audio. No Rival or OBS changes.')
    out.mkdir(parents=True)
    cards = []
    school_root = Path('build')/specs['school']
    for offset in (0, 7, 14, 18, 39):
        cards.append(f'<h3>School return: enable +{offset}</h3><div class="grid">')
        for side in ('nes', 'snes'):
            name = f'{side}-{offset:02d}.png'
            source = school_root/name
            if sha(source) != reports['school']['artifacts'][name]:
                raise ValueError('Changed school collage')
            shutil.copyfile(source, out/name)
            sources[str(source)] = sha(source)
            cards.append(f'<figure><img src="{name}"><figcaption>{side.upper()}</figcaption></figure>')
        cards.append('</div>')
    for policy in reports['combat']['policies']:
        clip = reports['combat']['policies'][policy]['listening_excerpt']
        source = Path('build')/specs['combat']/clip['file']
        if sha(source) != clip['sha256']:
            raise ValueError('Changed native excerpt')
        shutil.copyfile(source, out/source.name)
        sources[str(source)] = sha(source)
        cards.append(f'<p>{policy}, unprocessed emulator PCM:</p><audio controls preload="none" src="{source.name}"></audio>')
    for name in (__file__, 'tools/audit_display_cadence.py', 'tools/audit_uniform_holds.py',
                 'tools/audit_main_display_latency.py', 'tools/benchmark_report.py',
                 'tools/audit_room_entry.py', 'tests/test_camera_guard_reprobe.py'):
        sources[str(name)] = sha(Path(name))
    if any(sha(Path(p)) != digest for p, digest in sources.items()):
        raise ValueError('Sources changed during review')
    page = '<!doctype html><meta charset="utf-8"><title>Camera deadline reprobe</title><style>body{font:17px system-ui;background:#101820;color:#eef;max-width:1150px;margin:30px auto}a{color:#8df}.grid{display:flex}img{width:384px;image-rendering:pixelated}pre{white-space:pre-wrap}audio{width:100%}</style>'
    page += '<h1>Sustained-combat timing fixed in this test; qualification still open</h1><p>'+html.escape(result['scope'])+'</p>'
    page += '<p><a href="report.json">Source-bound results</a> · <a href="manifest.json">Artifact hashes</a> · <a href="../camera-guard-combat-review-2232/">Every remaining combat failure: collages and audio</a> · <a href="../wub-tail-review-2099/">Physical splash audition</a></p>'
    page += '<p>1,661 sustained-combat loops pass. 1,752 admitted graphics services finish before VBlank; two late jobs are deferred and served exactly once. All 3,510 eligible stable frames have one NMI. Running/jumping retains 15-, 23-, and 3-frame outliers. These are measured episodes, not full-game speed certification.</p>'
    page += '<h2>Qualification and retained holds</h2><pre>'+html.escape(json.dumps({k: result[k] for k in ('oracle','school_gates','forward_gates','renderer','holds','audio')}, indent=2))+'</pre>'+''.join(cards)
    (out/'index.html').write_text(page)
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    (out/'manifest.json').write_text(json.dumps(dict(sources=sources,
        artifacts={p.name: sha(p) for p in out.iterdir() if p.is_file()}, release_ready=False), indent=2)+'\n')
    print(json.dumps(dict(out=str(out), scheduling=spans['passed'], combat=result['combat']['passed'],
                         sources=len(sources), release_ready=False)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    build(**vars(parser.parse_args()))
