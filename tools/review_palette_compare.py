"""Join exact comparator evidence to school, route, renderer, combat and DSP tests."""
import argparse
import csv
import html
import json
from pathlib import Path
import shutil
import struct

from tools.audit_main_display_latency import bound_report
from tools.audit_park_instructions import parse
from tools.audit_palette_pipeline import generations
from tools.audit_school_return import first_return
from tools.audit_shift_fade_schedule import marks
from tools.benchmark_report import sha, verify_capture
from tools.capture_school_instructions import equivalent
from tools.school_return_campaign import installed


def palette_sections(rows, entry, sprites):
    result = []
    for i, start in enumerate(rows):
        if start['pc'] != entry:
            continue
        end = next((r for r in rows[i+1:] if r['pc'] == sprites and r['s'] == start['s']), None)
        if end is None:
            raise ValueError('Truncated palette phase')
        if any(r['opcode'] == 0x40 for r in rows[i:] if r['clock'] < end['clock']):
            raise ValueError('Interrupted palette phase')
        result.append(dict(start=start, after=end, clocks=end['clock']-start['clock']))
    if not result:
        raise ValueError('Missing actual palette phases')
    return result


def build(out):
    if out.exists():
        raise ValueError('Fresh output required')
    sources = {}
    systems = {}
    for label, rom, cap, normal in (
        ('parent', 'oam-hide-tail-trial-2186', 'oam-hide-tail-instructions-2192',
         'oam-hide-tail-instruction-control-2191'),
        ('trial', 'palette-compare-trial-2197', 'palette-compare-instructions-2203',
         'palette-compare-instruction-control-2202')):
        rom, cap, normal = (Path('build')/p for p in (rom, cap, normal))
        for root in (cap, normal):
            sources.update(bound_report(root/'instruction-control.json')['sources'])
            for name in ('instruction-control.json', 'capture.json', 'timeline.json'):
                sources[str(root/name)] = sha(root/name)
        with installed():
            receipt, timeline = verify_capture(cap)
            baseline, plain = verify_capture(normal)
        equivalent(receipt, timeline, baseline, plain)
        if receipt['rom_sha256'] != sha(rom/'native-cpu.sfc'):
            raise ValueError('Different observed cartridge')
        binding = receipt['instruction_trace']
        trace = Path(binding['path'])
        if sha(trace) != binding['sha256']:
            raise ValueError('Changed instructions')
        with trace.open() as stream:
            rows = parse(csv.reader(stream), binding['first'], binding['last'])
        boot = {r.split()[2].lstrip('.'): int(r.split()[1], 16)
                for r in (rom/'native_boot.lbl').read_text().splitlines()}
        runtime = {r.split()[2].lstrip('.'): int(r.split()[1], 16)
                   for r in (rom/'native_runtime.lbl').read_text().splitlines()}
        index, anchors = first_return(timeline)
        colors = struct.unpack_from('<64H', (rom/'native-cpu.sfc').read_bytes(), boot['native_palette'])
        systems[label] = dict(observer_neutral=True, frames=receipt['frames'], anchors=anchors,
            generations=generations(timeline[index:index+40], colors),
            phases=palette_sections(rows, 0xC00000+boot['prepare_palette'], 0xC00000+boot['prepare_sprites']),
            marks=marks(rows, anchors['enable_frame'], runtime['gameplay_iteration_start']))
    reference = Path('build/school-return-nes-2140')
    sources.update(bound_report(reference/'school-return-report.json')['sources'])
    with installed():
        _, rows = verify_capture(reference)
    index, _ = first_return(rows)
    nes_generations = generations(rows[index:index+40], colors)
    for system in systems.values():
        if any(system['generations'][level]['source_indices'] != nes_generations[level]['source_indices']
               for level in range(4)):
            raise ValueError('Different generated fade palette')
    for name in ('school-return-report.json', 'capture.json', 'timeline.json'):
        sources[str(reference/name)] = sha(reference/name)
    specs = dict(oracle='palette-compare-oracle-2199', school='palette-compare-school-audit-2200',
        parent_school='oam-hide-tail-school-audit-2190', renderer='palette-compare-render-audit-2211',
        cadence='palette-compare-cadence-2212', combat='palette-compare-combat-review-2214')
    reports = {}
    for label, directory in specs.items():
        root = Path('build')/directory
        report = bound_report(root/'report.json')
        reports[label] = report
        sources.update(report['sources'])
        sources[str(root/'report.json')] = sha(root/'report.json')
        for name, digest in report.get('artifacts', {}).items():
            if sha(root/name) != digest:
                raise ValueError('Changed '+label+' artifact')
    # Audio report nests each run's binding; validate both explicitly.
    audio_root = Path('build/palette-compare-audio-2210')
    audio = bound_report(audio_root/'report.json')
    sources.update(audio['sources'])
    for label in ('baseline', 'candidate'):
        for name, digest in audio[label]['sources'].items():
            if sha(Path(name)) != digest:
                raise ValueError('Changed DSP source')
            sources[name] = digest
    sources[str(audio_root/'report.json')] = sha(audio_root/'report.json')
    # Same-core controls are explicit for each observer kind.
    pairs = [('palette-compare-dsp-2205', 'palette-compare-route-2201'),
             ('palette-compare-main-2207', 'palette-compare-main-normal-2206'),
             ('palette-compare-render-2209', 'palette-compare-render-normal-2208')]
    for observed, normal in pairs:
        receipts = [verify_capture(Path('build')/p)[0] for p in (observed, normal)]
        if receipts[0]['core_sha256'] != receipts[1]['core_sha256']:
            raise ValueError('Observer control uses different core')
    forward_root = Path('build/palette-compare-entry-2204')
    forward = json.loads((forward_root/'report.json').read_text())
    for side, root in (('nes', Path('build/park-single-nes-331')),
                       ('snes', Path('build/palette-compare-route-2201'))):
        receipt, _ = verify_capture(root)
        if forward['sources'][side] != dict(rom_sha256=receipt['rom_sha256'],
                                          capture_sha256=sha(root/'capture.json')):
            raise ValueError('Changed forward entry capture')
        sources[str(root/'capture.json')] = sha(root/'capture.json')
    if forward['audit_sha256'] != sha(Path('tools/audit_room_entry.py')):
        raise ValueError('Changed forward entry auditor')
    sources[str(forward_root/'report.json')] = sha(forward_root/'report.json')
    # Copy only authenticated existing images/audio; no resampling or alignment.
    out.mkdir(parents=True)
    cards = []
    for offset in (0, 7, 9, 14, 18, 24, 29, 39):
        cards.append(f'<h3>Return fade at enable +{offset}</h3><div class="grid">')
        for label, kind, side in (('NES', 'school', 'nes'), ('Parent', 'parent_school', 'snes'),
                                  ('Trial', 'school', 'snes')):
            root = Path('build')/specs[kind]
            source = root/f'{side}-{offset:02d}.png'
            if sha(source) != reports[kind]['artifacts'][source.name]:
                raise ValueError('Changed collage input')
            target = f'{label.lower()}-{offset:02d}.png'
            shutil.copyfile(source, out/target)
            sources[str(source)] = sha(source)
            cards.append(f'<figure><img src="{target}"><figcaption>{label}</figcaption></figure>')
        cards.append('</div>')
    for name, root in (('parent', Path('build/oam-hide-tail-instruction-control-2191')),
                       ('trial', Path('build/palette-compare-instruction-control-2202'))):
        sources[str(root/'audio.wav')] = sha(root/'audio.wav')
        shutil.copyfile(root/'audio.wav', out/f'{name}.wav')
    for name in (__file__, 'tools/audit_main_display_latency.py', 'tools/audit_park_instructions.py',
                 'tools/audit_palette_pipeline.py', 'tools/audit_school_return.py',
                 'tools/audit_shift_fade_schedule.py', 'tools/benchmark_report.py',
                 'tools/capture_school_instructions.py', 'tools/school_return_campaign.py',
                 'tools/audit_room_entry.py'):
        p = Path(name)
        sources[str(p)] = sha(p)
    if any(sha(Path(p)) != h for p, h in sources.items()):
        raise ValueError('Sources changed during review')
    result = dict(systems=systems, nes_generations=nes_generations,
        oracle_cases=sum(c['cases'] for c in reports['oracle']['cases']),
        oracle_mutants=reports['oracle']['mutants'], school_gates=reports['school']['gates'],
        forward_gates=forward['gates'], renderer={k: v for k, v in reports['renderer'].items()
            if k not in ('sources', 'images')},
        cadence=dict(passed=reports['cadence']['passed'], rooms={k:len(v['iterations'])
            for k, v in reports['cadence']['main']['rooms'].items()}, holds=reports['cadence']['holds']),
        combat=dict(passed=reports['combat']['passed'], outliers=reports['combat']['outliers'],
                    policies={k:dict(passed=v['passed'], iterations=len(v['iterations']))
                              for k, v in reports['combat']['policies'].items()}),
        audio={k: v for k, v in audio['candidate'].items() if k not in ('events', 'sources')},
        sources=sources, deployed=False, release_ready=False, full_game_speed_verified=False,
        scope='School return now matches all40 NES fade frames and both whole-load limits. '
        'Forward entries, actual renderer coverage, stable cadence, strict combat and native DSP '
        'transport are reported separately, including every failure/long hold. Independent encounters '
        'are not identical workloads. Core observers are neutral to same-core controls. Comparator '
        'oracle is not an injected-interrupt proof. Native PCM is unprocessed, not a pop-free verdict. '
        'No Rival/OBS changes, relaxed thresholds, game timer edits or new graphics.')
    page = '<!doctype html><meta charset="utf-8"><title>School-return fade corrected</title><style>body{font:17px system-ui;background:#101820;color:#eef;max-width:1250px;margin:30px auto}a{color:#8df}td,th{padding:8px;border:1px solid #567}.grid{display:flex}.grid img{width:352px;image-rendering:pixelated}figure{margin:12px}pre{white-space:pre-wrap}</style>'
    page += '<h1>School-return fade corrected; full qualification remains open</h1><p>'+html.escape(result['scope'])+'</p><p><a href="report.json">Source-bound measurements</a> · <a href="../palette-compare-entry-2204/">Forward fades</a> · <a href="../palette-compare-render-audit-2211/">Renderer</a> · <a href="../palette-compare-combat-review-2214/">Combat failures and audio</a></p>'
    page += '<p>17,408 executed comparator cases pass; three executed mutants fail. Palette generation moves from +7/11/15/19 to NES +6/10/14/18. The first main iteration now finishes/resets on +3 before the interrupt.</p>'
    page += '<h2>Every traced palette phase, including slower changed-palette paths</h2><table><tr><th>Build</th><th>Offset</th><th>Entry line</th><th>Elapsed clocks</th></tr>'+''.join(f'<tr><td>{name}</td><td>{p["start"]["frame"]-run["anchors"]["enable_frame"]}</td><td>{p["start"]["line"]}</td><td>{p["clocks"]}</td></tr>' for name, run in systems.items() for p in run['phases'])+'</table>'
    page += '<h2>Unprocessed emulator audio</h2>'+''.join(f'<p>{n}: <audio controls preload="none" src="{n}.wav"></audio></p>' for n in ('parent','trial'))
    page += '<h2>Qualification summary</h2><pre>'+html.escape(json.dumps({k: result[k] for k in ('school_gates','forward_gates','renderer','audio')}, indent=2))+'</pre>'+''.join(cards)
    (out/'index.html').write_text(page)
    result['artifacts'] = {p.name: sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(out=str(out), school=all(result['school_gates'].values()),
                         forward=all(result['forward_gates'].values()), combat=result['combat']['passed'])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    build(**vars(p.parse_args()))
