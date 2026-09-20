"""Audit an exact-state phase80 trial, including the first witnessed counter change."""
import argparse
import html
import json
from pathlib import Path
import shutil

from tools.benchmark_report import sha
from tools.review_combat_checkpoints import load
from tools.review_sprite_deadline import cadence


def with_initial(root, report, rows):
    memory = (root/'initial.ram').read_bytes()
    if len(memory) != 131072:
        raise ValueError('Need full initial WRAM')
    return [dict(frame=report['restored_frame'], game_ram_hex=memory[:2048].hex()), *rows]


def review(control, trial, out):
    if out.exists():
        raise ValueError('Fresh output required')
    before, a = load(control)
    after, b = load(trial)
    if (not before['passed'] or before['trial'] is not None or
            not after['cross_rom_restore_verified'] or
            after['trial']['variant'] != 'fused-phase80' or
            Path(after['trial']['resume_control']) != control or
            before['initial_registers'] != after['initial_registers'] or
            (control/'initial.ram').read_bytes() != (trial/'initial.ram').read_bytes() or
            (control/'two-port-input.json').read_bytes() != (trial/'two-port-input.json').read_bytes() or
            [r['frame'] for r in a] != [r['frame'] for r in b]):
        raise ValueError('Different or unqualified initial state / inputs / window')
    old = cadence(with_initial(control, before, a))
    new = cadence(with_initial(trial, after, b))
    gates = dict(parent_stall_reproduced=any(s['frames'] > 2 for s in old['intervals']),
                 candidate_all_two_frames=new['all_two_frames'],
                 no_fewer_completions=len(new['completions']) >= len(old['completions']),
                 no_faults=all(r['checks']['faults_clear'] for r in a+b))
    differences = [dict(frame=x['frame'], equal={k: x[k] == y[k] for k in
                   ('video_sha256', 'ram_sha256', 'registers', 'audio_sha256')})
                   for x, y in zip(a, b)]
    sources = {}
    for root, report in ((control, before), (trial, after)):
        sources.update(report['sources'])
        for name in ('report.json', 'timeline.json', 'initial.ram', 'two-port-input.json', 'audio.wav'):
            sources[str(root/name)] = sha(root/name)
    for path in (Path(__file__), Path('tools/review_combat_checkpoints.py'),
                 Path('tools/review_sprite_deadline.py'), Path('tools/benchmark_report.py')):
        sources[str(path)] = sha(path)
    out.mkdir()
    cards = []
    stalled = next((s for s in old['intervals'] if s['frames'] > 2), old['intervals'][0])
    selected = range(max(a[0]['frame'], stalled['first']-1), min(a[-1]['frame'], stalled['last']+2)+1)
    for frame in selected:
        cards.append(f'<h3>Physical frame {frame}</h3><div class="pair">')
        for label, root, rows in (('phase96', control, a), ('phase80', trial, b)):
            row = next(r for r in rows if r['frame'] == frame)
            source = root/row['frame_image']
            if sha(source) != row['frame_image_sha256']:
                raise ValueError('Changed frame')
            name = f'{label}-{frame}.png'
            shutil.copyfile(source, out/name)
            sources[str(source)] = sha(source)
            cards.append(f'<figure><img src="{name}"><figcaption>{label}</figcaption></figure>')
        cards.append('</div>')
    for name, root in (('before', control), ('after', trial)):
        shutil.copyfile(root/'audio.wav', out/(name+'.wav'))
    report = dict(symptom_improved=all(gates.values()), gates=gates, before=old, after=new,
                  full_frame_differences=differences, frames=len(a), sources=sources,
                  identical_frames={k: sum(r['equal'][k] for r in differences)
                                    for k in differences[0]['equal']},
                  rom_sha256=after['trial']['trial_rom_sha256'],
                  parent_rom_sha256=after['trial']['parent_rom_sha256'],
                  control=str(control), trial=str(trial), release_ready=False,
                  original_nes_equivalence=False, pop_free_audio_verified=False, hardware_tested=False,
                  scope='Exact complete WRAM, CPU registers and two-port input at restoration. '
                  'Same-ROM control exactly reproduces uninterrupted video/state/input/PCM. '
                  'Initial WRAM is included to witness the first completion; incomplete boundary '
                  'intervals remain excluded. Every interior interval and subsequent output difference '
                  'is retained. Earlier admission changes only eight compare operands and checksum. '
                  'This narrow improvement does not qualify full-route scrolling, audio or hardware.')
    page = '<!doctype html><meta charset="utf-8"><title>Earlier-start combat timing</title>'
    page += '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}a{color:#8df}.pair{display:flex}figure{margin:8px;flex:1}img,audio{width:100%}img{image-rendering:pixelated}</style>'
    page += '<h1>Earlier-start combat timing: exact encounter</h1><p>'+html.escape(report['scope'])+'</p>'
    page += '<p>Witnessed completion intervals: phase96 '+html.escape(str(old['histogram']))
    page += '; phase80 '+html.escape(str(new['histogram']))+'.</p>'
    page += '<p>Whole-frame equality counts: '+html.escape(str(report['identical_frames']))+f' / {len(a)}.</p>'
    page += '<p><a href="report.json">All differences, cadence and source hashes</a></p>'
    page += '<h2>Entire unprocessed native audio (not graded pop-free)</h2><p>Before</p><audio controls src="before.wav"></audio>'
    page += '<p>After</p><audio controls src="after.wav"></audio>'+''.join(cards)
    (out/'index.html').write_text(page)
    if any(sha(Path(p)) != digest for p, digest in sources.items()):
        raise ValueError('Changed source')
    report['artifacts'] = {p.name: sha(p) for p in out.iterdir() if p.is_file()}
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(gates=gates, before=old['histogram'], after=new['histogram'])))
    return report['symptom_improved']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('control', 'trial', 'out'):
        parser.add_argument('--'+key, type=Path, required=True)
    raise SystemExit(0 if review(**vars(parser.parse_args())) else 1)
