"""Review an exact-start-state sprite deadline experiment, not release qualification."""
import argparse
from collections import Counter
import html
import json
from pathlib import Path
import shutil

from tools.benchmark_report import sha
from tools.review_combat_checkpoints import load


def cadence(rows):
    if len(rows) < 3 or any(b['frame'] != a['frame'] + 1 for a, b in zip(rows, rows[1:])):
        raise ValueError('Missing consecutive replay frames')
    values = [bytes.fromhex(r['game_ram_hex']) for r in rows]
    if any(len(r) != 2048 for r in values):
        raise ValueError('Incomplete game RAM')
    changes = []
    for i in range(1, len(rows)):
        delta = (values[i][0x52b] - values[i-1][0x52b]) & 255
        if delta not in (0, 1):
            raise ValueError('Skipped or reset completion counter')
        if delta:
            changes.append(rows[i]['frame'])
    spans = [dict(first=a, last=b, frames=b-a) for a, b in zip(changes, changes[1:])]
    return dict(completions=changes, intervals=spans,
                histogram=dict(Counter(s['frames'] for s in spans)),
                all_two_frames=bool(spans) and all(s['frames'] == 2 for s in spans),
                scope='Frame-end original $052B changes, not instruction timestamps. '
                      'First sample is not itself a witnessed change; incomplete boundary '
                      'intervals excluded. Every witnessed interior change retained.')


def review(control, trial, out):
    if out.exists():
        raise ValueError('Fresh output required')
    before, a = load(control)
    after, b = load(trial)
    if (not before['passed'] or before['trial'] is not None or
            not after['cross_rom_restore_verified'] or
            after['trial']['variant'] != 'sprite-fused-guarded' or
            Path(after['trial']['resume_control']) != control or
            before['initial_registers'] != after['initial_registers'] or
            (control/'initial.ram').read_bytes() != (trial/'initial.ram').read_bytes() or
            (control/'two-port-input.json').read_bytes() != (trial/'two-port-input.json').read_bytes() or
            [r['frame'] for r in a] != [r['frame'] for r in b]):
        raise ValueError('Different or unqualified initial state, window, or two-player input')
    old, new = cadence(a), cadence(b)
    gates = dict(original_stall_reproduced=any(s['frames'] == 3 for s in old['intervals']),
                 trial_all_two_frames=new['all_two_frames'],
                 no_fewer_completions=len(new['completions']) >= len(old['completions']))
    differences = [dict(frame=x['frame'],
                        equal={k: x[k] == y[k] for k in
                               ('video_sha256', 'ram_sha256', 'registers', 'audio_sha256')})
                   for x, y in zip(a, b)]
    sources = {}
    for root, report in ((control, before), (trial, after)):
        sources.update(report['sources'])
        for name in ('report.json', 'timeline.json', 'initial.ram', 'two-port-input.json', 'audio.wav'):
            sources[str(root/name)] = sha(root/name)
    for p in (Path(__file__), Path('tools/review_combat_checkpoints.py'),
              Path('tools/audit_main_display_latency.py'), Path('tools/benchmark_report.py')):
        sources[str(p)] = sha(p)
    out.mkdir()
    cards = []
    for frame in (2238, 2239, 2240, 2241, 2242, 2243, 2244):
        cards.append(f'<h3>Absolute frame {frame}</h3><div class="pair">')
        for label, root, rows in (('before', control, a), ('after', trial, b)):
            row = next(r for r in rows if r['frame'] == frame)
            source = root/row['frame_image']
            name = f'{label}-{frame}.png'
            shutil.copyfile(source, out/name)
            sources[str(source)] = sha(source)
            cards.append(f'<figure><img src="{name}"><figcaption>{label}</figcaption></figure>')
        cards.append('</div>')
    for name, root in (('before', control), ('after', trial)):
        shutil.copyfile(root/'audio.wav', out/(name+'.wav'))
    report = dict(symptom_improved=all(gates.values()), gates=gates, before=old, after=new,
                  full_frame_differences=differences,
                  identical_frames={k: sum(r['equal'][k] for r in differences)
                                    for k in differences[0]['equal']},
                  frames=len(a), rom_sha256=after['trial']['trial_rom_sha256'],
                  parent_rom_sha256=after['trial']['parent_rom_sha256'],
                  control=str(control), trial=str(trial), sources=sources,
                  release_ready=False, original_nes_equivalence=False,
                  pop_free_audio_verified=False, hardware_tested=False,
                  scope=__doc__+' Same-ROM control reproduces uninterrupted pixels, RAM, '
                        'registers, inputs and native PCM across the whole 80-frame window. '
                        'Trial begins from the same complete WRAM and saved registers, using '
                        'a freshly rebuilt permitted ROM patch. Changed later execution, '
                        'pictures and PCM are retained, not an equality PASS. Native audio '
                        'below is the entire unprocessed replay, not certified pop-free. '
                        'Longer independent combat still fails its strict gate; other '
                        'rendering, DMA, menus and audio checks are not inherited from a parent.')
    page = '<!doctype html><meta charset="utf-8"><title>Sprite-copy deadline: exact encounter</title>'
    page += '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}a{color:#8df}.pair{display:flex}figure{margin:8px;flex:1}img,audio{width:100%}img{image-rendering:pixelated}</style>'
    page += '<h1>Sprite-copy deadline: exact encounter</h1><p>'+html.escape(report['scope'])+'</p>'
    page += '<p>Witnessed interior completion intervals: before '+html.escape(str(old['histogram']))
    page += '; after '+html.escape(str(new['histogram']))+'. First sample is left-censored.</p>'
    page += '<p>The former 2239→2242 update now completes at 2241. This is a narrow improvement, not release approval.</p>'
    page += '<p>Whole-frame equal counts: '+html.escape(str(report['identical_frames']))+' / 80.</p>'
    page += '<p><a href="report.json">All differences, completion frames, exact ROM and source hashes</a></p>'
    page += '<h2>Unprocessed native audio</h2><p>Before</p><audio controls src="before.wav"></audio>'
    page += '<p>After</p><audio controls src="after.wav"></audio>'+''.join(cards)
    (out/'index.html').write_text(page)
    if any(sha(Path(p)) != h for p, h in sources.items()):
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
