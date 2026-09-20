"""Source-bound sprite-hide timing, executed oracle and retained game regressions."""
import argparse
import csv
import html
import json
from pathlib import Path
import shutil
import struct

from tools.audit_main_display_latency import bound_report
from tools.audit_park_instructions import parse
from tools.audit_alley_entry_work import return_index
from tools.audit_palette_pipeline import generations
from tools.audit_room_load_profile import interrupt_accounting
from tools.audit_school_return import first_return
from tools.audit_shift_fade_schedule import marks
from tools.benchmark_report import sha, verify_capture
from tools.capture_school_instructions import equivalent
from tools.school_return_campaign import installed


def hide_calls(rows):
    calls = []
    for i, start in enumerate(rows):
        if start['pc'] != 0xC7DFE2:
            continue
        end = return_index(rows, i, 0x60)
        # The replacement entry jumps to the same absolute LDX in its helper.
        load = i if start['opcode'] == 0xAE else i+1
        if rows[load]['opcode'] != 0xAE or rows[load]['pc'] not in (0xC7DFE2, 0xC77C00):
            raise ValueError('Unexpected count-load entry')
        count = rows[load+1]['x']
        if count % 4 or count > 252 or rows[end]['pc'] != 0xC7F299:
            raise ValueError('Not a complete aligned main-loop sprite-hide call')
        if any(r['opcode'] == 0x40 for r in rows[i:end]):
            raise ValueError('Interrupted hide call needs separate attribution')
        calls.append(dict(start=start, after=rows[end], count=count,
            elapsed_master_clocks=rows[end]['clock']-start['clock']))
    if not calls:
        raise ValueError('Missing actual sprite-hide calls')
    return calls


def build(out):
    if out.exists():
        raise ValueError('Fresh review required')
    sources = {}
    runs = {}
    timelines = {}
    for name, candidate, capture, normal in (
        ('parent', 'render-edge-trial-2172', 'edge-school-instructions-2185',
         'edge-school-instruction-control-2184'),
        ('trial', 'oam-hide-tail-trial-2186', 'oam-hide-tail-instructions-2192',
         'oam-hide-tail-instruction-control-2191')):
        candidate, capture, normal = (Path('build')/p for p in (candidate, capture, normal))
        binding = bound_report(capture/'instruction-control.json')
        sources.update(binding['sources'])
        sources.update(bound_report(normal/'instruction-control.json')['sources'])
        with installed():
            receipt, timeline = verify_capture(capture)
            baseline, plain = verify_capture(normal)
        equivalent(receipt, timeline, baseline, plain)
        trace = Path(receipt['instruction_trace']['path'])
        if sha(trace) != receipt['instruction_trace']['sha256']:
            raise ValueError('Changed instruction trace')
        if sha(candidate/'native-cpu.sfc') != receipt['rom_sha256']:
            raise ValueError('Wrong observed cartridge')
        with trace.open() as stream:
            rows = parse(csv.reader(stream), binding['first'], binding['last'])
        index, anchors = first_return(timeline)
        enable = anchors['enable_frame']
        boot = {r.split()[2].lstrip('.'): int(r.split()[1], 16)
                for r in (candidate/'native_boot.lbl').read_text().splitlines()}
        runtime = {r.split()[2].lstrip('.'): int(r.split()[1], 16)
                   for r in (candidate/'native_runtime.lbl').read_text().splitlines()}
        # Color mapping is read from the actual cartridge, not an unbound include.
        image = (candidate/'native-cpu.sfc').read_bytes()
        colors = struct.unpack_from('<64H', image, boot['native_palette'])
        gens = generations(timeline[index:index+40], colors)
        nmis = {r['clock']: r['pc'] for r in rows
                if r['pc'] in (boot['nmi'], boot['nmi']+0xC00000)}
        start = next(i for i, r in enumerate(rows)
                     if r['pc'] == 0xC7F2C6 and r['frame'] >= enable+3)
        end = next(i for i in range(start+1, len(rows)) if rows[i]['pc'] == 0xC7F2C9)
        tail = interrupt_accounting(rows[start:end+1], nmis)
        runs[name] = dict(observer_neutral=True, frames=receipt['frames'],
            anchors=anchors, hide_calls=hide_calls(rows), generations=gens,
            marks=marks(rows, enable, runtime['gameplay_iteration_start']),
            last_main_call=dict(start=rows[start], after=rows[end], **tail))
        timelines[name] = timeline
        for p in (capture/'instruction-control.json', normal/'instruction-control.json',
                  capture/'timeline.json', normal/'timeline.json'):
            sources[str(p)] = sha(p)
    nes = Path('build/school-return-nes-2140')
    sources.update(bound_report(nes/'school-return-report.json')['sources'])
    with installed():
        _, original = verify_capture(nes)
    index, _ = first_return(original)
    nes_generations = generations(original[index:index+40], colors)
    for level in range(4):
        if any(r['generations'][level]['source_indices'] != nes_generations[level]['source_indices']
               for r in runs.values()):
            raise ValueError('Different source fade palette')
    a, b = (runs[n]['hide_calls'] for n in ('parent', 'trial'))
    if len(a) != len(b) or any(x['count'] != y['count'] for x, y in zip(a, b)):
        raise ValueError('Different hide-call counts; do not claim matched-work savings')
    timing = [dict(count=x['count'], parent=x['elapsed_master_clocks'],
                   trial=y['elapsed_master_clocks'],
                   saved=x['elapsed_master_clocks']-y['elapsed_master_clocks'])
              for x, y in zip(a, b)]
    proofroot = Path('build/oam-hide-tail-oracle-2189')
    proof = bound_report(proofroot/'report.json')
    if not proof['passed']:
        raise ValueError('Failed machine-code oracle')
    for name, digest in proof['artifacts'].items():
        if sha(proofroot/name) != digest:
            raise ValueError('Changed executed oracle artifact')
    sources.update(proof['sources'])
    school = Path('build/oam-hide-tail-school-audit-2190')
    failure = bound_report(school/'report.json')
    sources.update(failure['sources'])
    route = Path('build/oam-hide-tail-route-2193')
    forward = Path('build/oam-hide-tail-entry-2194')
    entry = json.loads((forward/'report.json').read_text())
    for label, root in (('nes', Path('build/park-single-nes-331')), ('snes', route)):
        receipt, _ = verify_capture(root)
        if entry['sources'][label] != dict(rom_sha256=receipt['rom_sha256'],
                                         capture_sha256=sha(root/'capture.json')):
            raise ValueError('Forward entry report binds different capture')
        sources[str(root/'capture.json')] = sha(root/'capture.json')
    if entry['audit_sha256'] != sha(Path('tools/audit_room_entry.py')):
        raise ValueError('Changed forward-entry auditor')
    for p in (proofroot/'report.json', school/'report.json', forward/'report.json',
              nes/'capture.json', nes/'timeline.json', nes/'school-return-report.json'):
        sources[str(p)] = sha(p)
    out.mkdir(parents=True)
    cards = []
    for offset in (0, 7, 9, 14, 18, 24, 29, 39):
        cards.append(f'<h3>School return, enable +{offset}</h3><div class="grid">')
        for side in ('nes', 'snes'):
            source = school/f'{side}-{offset:02d}.png'
            if sha(source) != failure['artifacts'][source.name]:
                raise ValueError('Changed failure screenshot')
            shutil.copyfile(source, out/source.name)
            sources[str(source)] = sha(source)
            cards.append(f'<figure><img src="{source.name}"><figcaption>{side}</figcaption></figure>')
        cards.append('</div>')
    for label, root in (('parent', Path('build/edge-school-instruction-control-2184')),
                        ('trial', Path('build/oam-hide-tail-instruction-control-2191'))):
        shutil.copyfile(root/'audio.wav', out/f'{label}.wav')
        sources[str(root/'audio.wav')] = sha(root/'audio.wav')
    for p in map(Path, (__file__, 'tools/audit_main_display_latency.py',
            'tools/audit_park_instructions.py', 'tools/audit_alley_entry_work.py',
            'tools/audit_palette_pipeline.py', 'tools/audit_room_load_profile.py',
            'tools/audit_school_return.py', 'tools/audit_shift_fade_schedule.py',
            'tools/audit_room_entry.py', 'tools/benchmark_report.py',
            'tools/capture_school_instructions.py', 'tools/school_return_campaign.py')):
        sources[str(p)] = sha(p)
    before, after = timelines['parent'], timelines['trial']
    comparisons = {key: sum(x[key] != y[key] for x, y in zip(before, after))
        for key in ('video_sha256', 'game_ram_hex', 'input_requested', 'input_delivered')}
    report = dict(systems=runs, timing=timing, nes_generations=nes_generations,
        game_differences=comparisons, equal_game_encounters=False,
        oracle_cases=sum(c['cases'] for c in proof['cases']), mutants=proof['mutants'],
        school_gates=failure['gates'], forward_gates=entry['gates'],
        sources=sources, release_ready=False, deployed=False,
        scope='Neutral full2872-frame instruction observers. All six complete hide calls have '
        'matching count and no interrupt; elapsed master clocks include emulator events. '
        'Game encounters/inputs differ between builds; routine savings are not whole-game ratios. '
        'School palette generation is still one frame later than NES. The measured final main '
        'call still crosses an ordinary NMI. All fixed-offset school failures retained. '
        'Forward route completes and all three entry comparisons pass, not full scrolling, '
        'combat, menu, interrupt-race or acoustic qualification. No Rival/OBS changes.')
    page = '<!doctype html><meta charset="utf-8"><title>Unused-sprite loop optimization</title><style>body{font:17px system-ui;background:#101820;color:#eef;max-width:1150px;margin:30px auto}a{color:#8df}td,th{padding:8px;border:1px solid #567}.grid{display:flex}.grid img{width:480px;image-rendering:pixelated}</style>'
    page += '<h1>Less CPU work; school-return timing still fails</h1><p>'+html.escape(report['scope'])+'</p><p><a href="report.json">All measurements and source hashes</a> · <a href="../oam-hide-tail-entry-2194/">Passing forward-entry comparison</a></p>'
    page += '<p>131,072 executed equivalence cases pass; three executed mutants are rejected. Full traversal completes8,874 frames. No release promotion.</p>'
    page += '<table><tr><th>Sprite count byte</th><th>Parent clocks</th><th>Trial clocks</th><th>Saved</th></tr>'+''.join('<tr>'+''.join(f'<td>{r[k]}</td>' for k in ('count','parent','trial','saved'))+'</tr>' for r in timing)+'</table>'
    page += '<h2>First four completed palette generations</h2><table><tr><th>Level</th><th>NES offset</th><th>Parent offset</th><th>Trial offset</th></tr>'+''.join(f'<tr><td>{i}</td><td>{nes_generations[i]["offset"]}</td><td>{runs["parent"]["generations"][i]["offset"]}</td><td>{runs["trial"]["generations"][i]["offset"]}</td></tr>' for i in range(4))+'</table>'
    page += '<h2>Native emulator audio, unprocessed</h2>'+''.join(f'<p>{n}: <audio controls preload="none" src="{n}.wav"></audio></p>' for n in ('parent','trial'))+''.join(cards)
    (out/'index.html').write_text(page)
    report['artifacts'] = {p.name: sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(out=str(out), calls=len(timing), first=timing[0],
                         school_passed=failure['passed'], forward_passed=entry['passed'])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    build(**vars(p.parse_args()))
