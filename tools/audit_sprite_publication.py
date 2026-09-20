"""Follow observed NES sprite generations through preparation, DMA and rendering.

Structural integrity is separate from latency: correct transfers can still
display old generations or omit intermediate generations. Nothing is retimed.
"""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import shutil

from tools.audit_main_display_latency import bound_report
from tools.audio_packet_log import labels
from tools.benchmark_report import sha, verify_capture
from tools.capture_combat_instructions import equivalent
from tools.frame_audit import verify_frame

FIELDS = ('kind', 'frame', 'line', 'cycle', 'pc', 'first_y', 'last_y', 'native_id',
          'ctrl', 'dirty', 'pending', 'blank', 'height', 'channel', 'mode', 'count',
          'source', 'target', 'remaining', 'game_oam', 'shadow', 'cached', 'prepared', 'oam')
SIZES = dict(game_oam=256, shadow=256, cached=256, prepared=544, oam=544)


def parse(raw):
    rows = []
    for index, row in enumerate(raw):
        if len(row) != len(FIELDS) or row[0] not in 'SPTDER':
            raise ValueError('Malformed sprite event')
        r = dict(zip(FIELDS, row))
        for key in FIELDS[1:19]: r[key] = int(r[key], 16 if key in ('pc', 'source') else 10)
        for key, size in SIZES.items():
            if len(bytes.fromhex(r[key])) != size: raise ValueError('Truncated sprite bytes')
        if not 0 <= r['line'] < 262 or r['height'] != 239 or r['blank'] not in (0, 1):
            raise ValueError('Unsupported beam/height')
        r['index'] = index; rows.append(r)
    if not rows: raise ValueError('Missing sprite events')
    return rows


def translated(source, ctrl, y_map, attr_map):
    if len(source) != 256 or len(y_map) != 256 or len(attr_map) != 256:
        raise ValueError('Missing complete sprite source/tables')
    output = bytearray()
    for i in range(0, 256, 4):
        y, tile, attr, x = source[i:i+4]
        output.extend((x, y_map[y], tile, attr_map[attr] | ((ctrl & 8) >> 3)))
    return bytes(output)


def analyze(events, first, last, y_map, attr_map):
    generations, failures, transfers, renders, preparation = [], [], [], [], []
    active_dma = None; displayed = None; pending_prepare = None
    coverage = {f: Counter() for f in range(first, last+1)}
    for e in events:
        if not first <= e['frame'] <= last: raise ValueError('Event outside window')
        kind = e['kind']
        if kind == 'S':
            if not generations or generations[-1]['source_hex'] != e['shadow']:
                generations.append(dict(id=len(generations), source_hex=e['shadow'],
                    source_event=e['index'], source_frame=e['frame'], source_line=e['line'],
                    source_cycle=e['cycle'], left_censored=not generations,
                    first_dma=None, first_render=None, rendered_frames=[]))
        elif kind == 'P':
            if pending_prepare is not None: failures.append(dict(event=e['index'], kind='nested_prepare'))
            pending_prepare = e
        elif kind == 'T':
            preparation.append(dict(start=pending_prepare['index'] if pending_prepare else None,
                end=e['index'], source_matches_cache=e['shadow'] == e['cached']))
            pending_prepare = None
        elif kind == 'D':
            if active_dma is not None: failures.append(dict(event=e['index'], kind='nested_dma'))
            if (e['channel'], e['mode'], e['count'], e['source'], e['target']) != (0, 0, 544, 0x7e5000, 4):
                raise ValueError('Unsupported OAM transfer; do not assume full linear copy')
            expected = translated(bytes.fromhex(e['cached']), e['ctrl'], y_map, attr_map)
            if bytes.fromhex(e['prepared'])[:256] != expected:
                failures.append(dict(event=e['index'], kind='prepared_translation'))
            generation = next((g for g in reversed(generations) if g['source_hex'] == e['cached']), None)
            active_dma = (e, generation)
        elif kind == 'E':
            if active_dma is None: raise ValueError('Unpaired DMA completion')
            begin, generation = active_dma
            if e['remaining'] or e['oam'] != begin['prepared']:
                failures.append(dict(event=e['index'], kind='actual_oam_transfer'))
            transfers.append(dict(start=begin['index'], end=e['index'], frame=e['frame'],
                generation=generation['id'] if generation is not None else None))
            if generation is not None and generation['first_dma'] is None:
                generation['first_dma'] = dict(event=e['index'], frame=e['frame'], line=e['line'], cycle=e['cycle'])
            displayed = (e, generation); active_dma = None
        elif kind == 'R':
            if e['blank'] or not 0 <= e['first_y'] <= e['last_y'] < e['height']:
                raise ValueError('Unsupported primary renderer span')
            coverage[e['frame']].update(range(e['first_y'], e['last_y']+1))
            generation = displayed[1] if displayed else None
            if displayed is not None and e['oam'] != displayed[0]['oam']:
                failures.append(dict(event=e['index'], kind='render_oam_changed_after_dma'))
            renders.append(dict(event=e['index'], frame=e['frame'], first_y=e['first_y'], last_y=e['last_y'],
                generation=generation['id'] if generation is not None else None,
                source_age_frames=e['frame']-generation['source_frame'] if generation is not None else None,
                oam_sha256=hashlib.sha256(bytes.fromhex(e['oam'])).hexdigest()))
            if generation is not None:
                if generation['first_render'] is None:
                    generation['first_render'] = dict(event=e['index'], frame=e['frame'], first_y=e['first_y'])
                if e['frame'] not in generation['rendered_frames']: generation['rendered_frames'].append(e['frame'])
    if active_dma is not None: failures.append(dict(kind='unfinished_dma'))
    for frame, lines in coverage.items():
        missing = sorted(set(range(239))-set(lines)); duplicate = sorted(k for k, v in lines.items() if v != 1)
        if missing or duplicate: failures.append(dict(kind='render_coverage', frame=frame, missing=missing, duplicate=duplicate))
    if not transfers or not generations or not preparation:
        raise ValueError('Missing source/preparation/DMA populations')
    for g in generations:
        g['source_sha256'] = hashlib.sha256(bytes.fromhex(g.pop('source_hex'))).hexdigest()
        g['source_to_first_render_frames'] = g['first_render']['frame']-g['source_frame'] if g['first_render'] else None
        g['newer_source_observed'] = g['id'] < len(generations)-1
    known = [g for g in generations if not g['left_censored']]
    return dict(structural_passed=not failures, failures=failures, first=first, last=last,
        generations=generations, transfers=transfers, preparation=preparation, renders=renders,
        source_to_first_render_histogram=dict(Counter(g['source_to_first_render_frames'] for g in known if g['first_render'])),
        known_source_generations=len(known),
        not_rendered_in_window=[g['id'] for g in known if not g['first_render']],
        right_censored_prepare=pending_prepare['index'] if pending_prepare else None,
        scope='First source is left-censored; unmatched initial display generations retained. '
              'Unrendered sources are retained, not excluded from latency coverage. '
              'Source ages are whole frame-number differences, not fitted elapsed CPU clocks. '
              'Structural PASS does not imply acceptable display latency or no dropped generations.')


def load(root, candidate):
    binding = bound_report(root/'sprite-events-capture.json')
    if not binding['observed'] or not binding['observer_neutral']:
        raise ValueError('Need observed same-core capture')
    receipt, rows = verify_capture(root); normal = Path(binding['reference'])
    control, before = verify_capture(normal); equivalent(receipt, rows, control, before)
    if receipt['rom_sha256'] != sha(candidate/'native-cpu.sfc'): raise ValueError('Wrong cartridge')
    symbols = labels(candidate/'native_boot.lbl'); rom = (candidate/'native-cpu.sfc').read_bytes()
    y_map = rom[symbols['sprite_y_map']:symbols['sprite_y_map']+256]
    attr_map = rom[symbols['sprite_attribute_map']:symbols['sprite_attribute_map']+256]
    with Path(binding['trace']).open() as stream: events = parse(csv.reader(stream))
    result = analyze(events, binding['first'], binding['last'], y_map, attr_map)
    return binding, rows, result, events


def audit(parent, trial, parent_candidate, trial_candidate, out):
    if out.exists(): raise ValueError('Fresh sprite review required')
    a = load(parent, parent_candidate); b = load(trial, trial_candidate)
    if (a[0]['first'], a[0]['last']) != (b[0]['first'], b[0]['last']): raise ValueError('Different windows')
    sources = dict(a[0]['sources'], **b[0]['sources'])
    # Genuine recorded trace corruption controls: changed transfer payload and
    # missing renderer coverage must not survive the structural oracle.
    symbols = labels(trial_candidate/'native_boot.lbl'); rom = (trial_candidate/'native-cpu.sfc').read_bytes()
    y_map = rom[symbols['sprite_y_map']:symbols['sprite_y_map']+256]
    attrs = rom[symbols['sprite_attribute_map']:symbols['sprite_attribute_map']+256]
    changed = [dict(e) for e in b[3]]; at = next(i for i, e in enumerate(changed) if e['kind'] == 'E')
    raw = bytearray.fromhex(changed[at]['oam']); raw[0] ^= 1; changed[at]['oam'] = raw.hex()
    bad_transfer = analyze(changed, b[0]['first'], b[0]['last'], y_map, attrs)
    at = next(e['index'] for e in b[3] if e['kind'] == 'R')
    missing = analyze([e for e in b[3] if e['index'] != at], b[0]['first'], b[0]['last'], y_map, attrs)
    controls = dict(changed_actual_oam_rejected=not bad_transfer['structural_passed'],
                    missing_render_span_rejected=not missing['structural_passed'])
    if not all(controls.values()): raise ValueError('Broken event control survived')
    comparison = []
    for ga, gb in zip(a[2]['generations'], b[2]['generations']):
        comparison.append(dict(parent=ga['id'], trial=gb['id'],
            same_source=ga['source_sha256'] == gb['source_sha256'],
            source_frames=[ga['source_frame'], gb['source_frame']],
            first_render_frames=[g['first_render']['frame'] if g['first_render'] else None for g in (ga, gb)]))
    out.mkdir(); cards = []
    # Every same-index renderer OAM difference within the entire fixed window.
    ar = {r['frame']: r for r in a[2]['renders']}; br = {r['frame']: r for r in b[2]['renders']}
    selected = [f for f in sorted(ar.keys() & br.keys()) if ar[f]['oam_sha256'] != br[f]['oam_sha256']]
    for frame in selected:
        cards.append(f'<h2>Changed displayed OAM · frame {frame}</h2><div class="pair">')
        for label, root, data in (('parent', parent, a), ('trial', trial, b)):
            path = verify_frame(root, data[1][frame-1]); sources[str(path)] = sha(path)
            name = f'{frame}-{label}.png'; shutil.copyfile(path, out/name)
            cards.append(f'<figure><img src="{name}"><figcaption>{label}</figcaption></figure>')
        cards.append('</div>')
    for p in (Path(__file__), Path('tests/test_sprite_publication.py'), Path('tools/frame_audit.py'),
              parent/'sprite-events-capture.json', trial/'sprite-events-capture.json',
              parent_candidate/'native-cpu.sfc', trial_candidate/'native-cpu.sfc'):
        sources[str(p)] = sha(p)
    report = dict(parent=a[2], trial=b[2], generation_comparison=comparison, controls=controls,
        sources=sources, displayed_oam_changed_frames=selected, release_ready=False, hardware_tested=False,
        scope=__doc__+' Fixed43-frame window1978–2020; not full-game coverage. '
              'No equal-work NES latency comparison has been made.')
    text = '<!doctype html><meta charset="utf-8"><title>Actual sprite publication</title>'
    text += '<style>body{background:#111a26;color:#eef;font:17px system-ui;max-width:1150px;margin:30px auto}a{color:#8df}.pair{display:flex}figure{margin:8px;flex:1}img{width:100%;image-rendering:pixelated}</style>'
    text += '<h1>Actual sprite preparation → DMA → display</h1><p>Fixed frame window; full-route observer/control equality. All source generations retained.</p>'
    for label, data in (('parent', a), ('trial', b)):
        r = data[2]
        text += f'<p>{label}: structural checks {r["structural_passed"]}; first-render delay histogram {r["source_to_first_render_histogram"]}; '
        text += f'{len(r["not_rendered_in_window"])} of {r["known_source_generations"]} known generations not rendered in the window.</p>'
    text += '<p>Correct DMA is not smooth animation: multi-frame display delays and omitted generations remain. '
    text += 'First source and pre-window display are explicitly censored. No original-NES or hardware equivalence claimed.</p>'
    text += '<p><a href="report.json">All events, generations, controls and bound sources</a></p>'+''.join(cards)
    (out/'index.html').write_text(text)
    report['artifacts'] = {p.name: sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: {field: report[k][field] for field in ('structural_passed',
        'source_to_first_render_histogram', 'known_source_generations', 'not_rendered_in_window')} for k in ('parent', 'trial')}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'trial', 'parent-candidate', 'trial-candidate', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    audit(**vars(p.parse_args()))
