"""Explain a fixed settling failure using working RAM, committed scroll and renderer lines.

This diagnostic does not change the original sweep selection or its failed gate.
"""
import argparse
import csv
import html
import json
from pathlib import Path
import shutil

from tools.audit_background_sweep import background_path, neutral
from tools.audit_park_instructions import parse
from tools.audit_render_scroll import bands, load_lines
from tools.audit_scroll_sweep import observations
from tools.benchmark_report import sha, verify_capture


def camera(row):
    raw = bytes.fromhex(row['game_ram_hex'])
    return dict(frame=row['frame'], phase=row['phase'], room=raw[0x42],
                working=int.from_bytes(raw[0xdc:0xde], 'little'),
                committed=raw[0xf6] | ((raw[0x3d] & 1) << 8),
                published=row['native']['hdma_street_scroll_x'])


def classify(first, stable, first_lines, stable_lines):
    """Never excuse a rendered split or an unpublished committed camera."""
    if set(first_lines) != set(range(32, 192)) or set(stable_lines) != set(range(32, 192)):
        raise ValueError('Incomplete renderer coverage')
    return (first['working'] == stable['working'] and first['room'] == stable['room']
            and first['working'] != first['committed']
            and first['committed'] == first['published']
            and stable['working'] == stable['committed'] == stable['published']
            and set(first_lines.values()) == {first['committed']}
            and set(stable_lines.values()) == {stable['committed']}
            and stable['frame'] > first['frame']+1)


def audit(sweep, background, normal, renderer, cpu, candidate, room, position, out):
    out.mkdir(parents=True, exist_ok=False)
    paths = dict(background=background, normal=normal, renderer=renderer, cpu=cpu)
    data = {name: verify_capture(path) for name, path in paths.items()}
    control, timeline = data['normal']
    if not neutral(data['background'], data['normal']):
        raise ValueError('Background observation changed execution')
    for name in ('renderer', 'cpu'):
        receipt, rows = data[name]
        if (rows != timeline or not receipt['capture_complete'] or
                any(receipt[k] != control[k] for k in
                    ('rom_sha256', 'scenario_sha256', 'audio_sha256', 'frames'))):
            raise ValueError('Observer changed execution: '+name)
    report_path = sweep/'report.json'
    original = json.loads(report_path.read_text())
    if original['sources']['snes']['capture_sha256'] != sha(background/'capture.json'):
        raise ValueError('Sweep does not bind background capture')
    selected, = [r for r in original['comparisons'] if (r['room'], r['camera']) == (room, position)]
    if selected['snes_settle'] <= selected['nes_settle']:
        raise ValueError('Selected sample is not a settling failure')
    firsts, stables, _ = observations(data['background'][1], True)
    first, stable = firsts[room, position], stables[room, position]
    if (stable['frame'] != selected['snes_frame'] or
            stable['frame']-first['frame'] != selected['snes_settle']):
        raise ValueError('Changed original sample selection')
    frames = [first['frame']-1, first['frame'], first['frame']+1, stable['frame']]
    trace = renderer.with_suffix('.csv')
    if data['renderer'][0]['render_scroll_trace']['sha256'] != sha(trace):
        raise ValueError('Unbound renderer trace')
    lines = load_lines(trace, 'snes', frames)
    records = {r['frame']: r for r in data['background'][1]}
    samples = [dict(**camera(records[f]), rendered=bands(lines[f])) for f in frames]
    diagnosed = classify(camera(first), camera(stable), lines[first['frame']], lines[stable['frame']])
    instruction = cpu.with_name(cpu.name+'-cpu.csv')
    receipt = data['cpu'][0]['instruction_trace']
    if receipt['sha256'] != sha(instruction):
        raise ValueError('Unbound CPU trace')
    with instruction.open() as stream:
        instructions = parse(csv.reader(stream), receipt['first'], receipt['last'])
    rom = candidate/'native-cpu.sfc'
    if sha(rom) != control['rom_sha256']:
        raise ValueError('Different candidate ROM')
    image = rom.read_bytes()
    # Pin the original camera arithmetic, not arbitrary opcode-looking bytes.
    expected = bytes.fromhex('a51a180865dc85dca5dd690028100269ff85dd')
    if image[0x7e140:0x7e140+len(expected)] != expected:
        raise ValueError('Camera arithmetic preimage changed')
    stores = [r for r in instructions if r['pc'] == 0xc7e146
              and r['frame'] == first['frame'] and r['a'] & 255 == position & 255]
    if len(stores) != 1:
        raise ValueError('No unique working-camera store at the failed first sample')
    store = stores[0]
    following = next(r for r in instructions if r['clock'] > store['clock'] and r['pc'] == 0xc7e148)
    if following['frame'] <= store['frame']:
        raise ValueError('Working-camera write did not span a captured frame boundary')
    result = dict(diagnosed_working_camera_transient=diagnosed,
        original_sweep_passed=original['passed'], original_sweep_gates=original['gates'],
        original_failed_sample=selected, samples=samples, cpu_store=store,
        next_original_instruction=following, observer_neutral=True,
        sources={str(p): sha(p) for p in [Path(__file__), Path('tools/audit_scroll_sweep.py'),
            Path('tools/audit_render_scroll.py'), Path('tools/audit_background_sweep.py'),
            Path('tools/audit_park_instructions.py'), report_path, trace, instruction, rom,
            *[p/'capture.json' for p in paths.values()]]},
        scope='Fixed original first/stable samples; no rematching or gate relaxation. '
              'All 160 playfield renderer lines are checked. CPU trace pins the interrupted '
              'original working-camera arithmetic. Explains this settling metric only; '
              'not a whole-game scroll, speed, or audio acceptance result.')
    cards = []
    for sample in samples:
        frame = sample['frame']
        path = background_path(background, records[frame])
        if path is None:
            raise ValueError('Unsupported background sample')
        name = f'frame-{frame}.png'
        shutil.copyfile(path, out/name)
        result['sources'][str(path)] = sha(path)
        cards.append(f'<figure><figcaption>Frame {frame}; working {sample["working"]}, '
                     f'committed {sample["committed"]}</figcaption><img src="{name}"></figure>')
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Camera transient diagnosis</title>'
        '<style>body{background:#101821;color:#eef;font:17px system-ui;margin:30px}a{color:#9df}'
        'section{display:flex;flex-wrap:wrap}figure{margin:10px}img{width:384px;image-rendering:pixelated}'
        'pre{white-space:pre-wrap}</style><h1>Working camera is not always a committed camera</h1><p>'
        +html.escape(result['scope'])+'</p><p>The original sweep remains failed. '
        '<a href="report.json">Full fixed-frame evidence</a></p><section>'+''.join(cards)+'</section><pre>'
        +html.escape(json.dumps(dict(diagnosed=diagnosed, samples=samples, store=store,
                                    resumed=following), indent=2))+'</pre>')
    print(json.dumps(dict(diagnosed=diagnosed, first_frame=first['frame'], stable_frame=stable['frame'],
                         original_sweep_passed=original['passed'])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('sweep', 'background', 'normal', 'renderer', 'cpu', 'candidate', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--room', type=int, required=True)
    p.add_argument('--position', type=int, required=True)
    audit(**vars(p.parse_args()))
