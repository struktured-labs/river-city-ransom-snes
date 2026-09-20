"""Contextualize a combat load against NES visibility without waiving cadence."""
import argparse
import html
import json
from pathlib import Path
import shutil

import numpy as np

from tools.audit_room_entry import load_anchors, no_later, rendering_mask, visibility_latencies, WINDOW
from tools.audit_scroll_publication import BACKGROUND_REGION, frame_path, rgb555
from tools.benchmark_report import sha, verify_capture
from tools.combat_campaign import POLICIES, verify_pair


def first_entry(rows, room):
    if room not in (1, 2, 3):
        raise ValueError('Need gameplay room1..3')
    for index in range(1, len(rows)):
        ram = bytes.fromhex(rows[index]['game_ram_hex'])
        if (ram[0x42] == room and ram[0x100] == 0xc0 and
                rendering_mask(rows[index]) & 8 and not rendering_mask(rows[index-1]) & 8):
            selected = rows[index:index+WINDOW]
            if len(selected) != WINDOW or any(bytes.fromhex(r['game_ram_hex'])[0x42] != room for r in selected):
                raise ValueError('First entry window truncated or leaves room; cannot select a later one')
            return index
    raise ValueError('No observed room rendering-enable edge')


def audit(reference, root, candidate, policy, room, out):
    original, nes = verify_capture(reference)
    port, combat, snes, normal = verify_pair(root, policy, 'snes', candidate)
    if (original['system'] != 'nes' or not original['capture_complete'] or
            original['rom_sha256'] != port['templates']['menu']['source_rom'] or
            any(r['fault'] or r['input_requested'] != r['input_delivered'] for r in nes+snes)):
        raise ValueError('Incomplete/faulty or unrelated original capture')
    out.mkdir(parents=True, exist_ok=False)
    results, pictures, cards, sources = {}, [], [], {}
    x0, y0, x1, y1 = BACKGROUND_REGION
    for system, directory, rows in (('nes', reference, nes), ('snes', normal, snes)):
        index = first_entry(rows, room)
        selected = rows[index:index+WINDOW]
        paths = [frame_path(directory, r) for r in selected]
        pixels = [rgb555(p)[y0:y1, x0:x1] for p in paths]
        visible = next((i for i, a in enumerate(pixels) if np.any(a)), None)
        anchors = load_anchors(rows, index)
        results[system] = dict(**anchors, first_nonblack_offset=visible,
                              **visibility_latencies(anchors, visible))
        pictures.append(pixels)
        for p in (directory/'capture.json', directory/'timeline.json', *paths):
            sources[str(p)] = sha(p)
        for offset in (0, 7, 10, 14, 18, 24, 29, 39):
            shutil.copyfile(paths[offset], out/f'{system}-{offset:02d}.png')
    differences = [int(np.any(a != b, axis=2).sum()) for a, b in zip(*pictures)]
    a, b = results['nes'], results['snes']
    gates = dict(fixed_fades_exact=not any(differences),
                 first_visible_no_later=no_later(a, b, 'first_nonblack_offset'),
                 room_change_no_later=no_later(a, b, 'room_change_to_visible'),
                 rendering_off_no_later=no_later(a, b, 'rendering_off_to_visible'))
    for kind in ('normal', 'observed'):
        p = root/f'{policy}-snes-{kind}'/'combat-observer.json'
        binding = json.loads(p.read_text())
        sources.update(binding['sources'])
        sources[str(p)] = sha(p)
    for name in (__file__, 'tools/audit_room_entry.py', 'tools/audit_scroll_publication.py',
                 'tools/benchmark_report.py', 'tools/combat_campaign.py', 'tools/audit_combat_loops.py'):
        sources[str(Path(name))] = sha(Path(name))
    report = dict(entry_passed=all(gates.values()), gates=gates, room=room, samples=results,
                  mismatch_pixels_by_offset=differences, strict_combat_passed=combat['passed'],
                  cadence_gate_waived=False, equal_work_verified=False, release_ready=False,
                  policies_equal=original['scenario_sha256'] == port['scenario_sha256'], sources=sources,
                  scope='First room rendering-enable edges and40 fixed background offsets; '
                  'whole load latency retained from room-change and rendering-off. Different '
                  'input policies and actor histories: a visibility comparison, not matched CPU '
                  'work or whole-game speed. No cadence failure removed or relabeled as passing.')
    for offset in (0, 7, 10, 14, 18, 24, 29, 39):
        cards.append(f'<h2>Enable +{offset}</h2><div class="grid">'+''.join(
            f'<figure><img src="{system}-{offset:02d}.png"><figcaption>{system}</figcaption></figure>'
            for system in ('nes', 'snes'))+'</div>')
    page = '<!doctype html><meta charset="utf-8"><title>Combat room entry versus NES</title>'
    page += '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}a{color:#8df}.grid{display:grid;grid-template-columns:1fr 1fr}figure{margin:8px}img{width:100%;image-rendering:pixelated}</style>'
    page += f'<h1>Room-entry visibility: {"PASS" if report["entry_passed"] else "FAIL"}</h1>'
    page += '<p>'+html.escape(report['scope'])+'</p><p>Strict combat pass: '+str(combat['passed'])+'. No gate waived.</p>'
    page += '<pre>'+html.escape(json.dumps(results, indent=2))+'</pre>'
    page += '<p><a href="report.json">Full measurements, source and artifact hashes</a></p>'+''.join(cards)
    (out/'index.html').write_text(page)
    report['artifacts'] = {p.name: sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ('entry_passed', 'strict_combat_passed', 'samples')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('reference', 'root', 'candidate', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--policy', choices=POLICIES, required=True)
    parser.add_argument('--room', type=int, choices=(1, 2, 3), required=True)
    audit(**vars(parser.parse_args()))
