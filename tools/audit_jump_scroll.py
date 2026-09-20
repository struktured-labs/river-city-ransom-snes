"""Compare RAM movement and visible scenery; do not infer loop timing from RAM snapshots."""
import argparse
from collections import Counter
import html
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image

from tools.audit_physical_camera import displacement
from tools.benchmark_report import sha, verify_capture
from tools.capture_jump_scroll import NAME, registered, scenario

ROI = (8, 32, 248, 56)  # School roof: no actors; identical native pixels, no scaling.
PHASES = ('jump_idle', 'jump_right', 'jump_left', 'jump_settle')


def changes(samples, field):
    """Reset at gaps/room/phase changes; keep all long stops and boundaries."""
    events, holds = [], []
    previous_event = None
    for a, b in zip(samples, samples[1:]):
        if b['frame'] != a['frame'] + 1 or (a['phase'], a['room']) != (b['phase'], b['room']):
            previous_event = None
            continue
        delta = b[field] - a[field]
        if not delta:
            continue
        event = dict(frame=b['frame'], delta=delta)
        events.append(event)
        if previous_event and previous_event['delta'] == delta:
            holds.append(dict(first_change=previous_event['frame'], next_change=b['frame'],
                              frames=b['frame']-previous_event['frame'], delta=delta))
        previous_event = event
    return dict(events=events, holds=holds, histogram=dict(Counter(h['frames'] for h in holds)),
                short_irregular=[h for h in holds if h['frames'] in (1, 3, 4)])


def picture_changes(samples, pairs):
    # Accepted picture displacement is relative, so use cumulative position
    # within each uninterrupted group only. Never bridge a rejected pair.
    rows, position = [], 0
    by_frame = {s['frame']: s for s in samples}
    for pair in pairs:
        if not pair['accepted']:
            continue
        s = by_frame[pair['frame']]
        position += pair['camera_delta']
        rows.append(dict(s, picture=position))
    return changes(rows, 'picture')


def load(directory):
    binding = json.loads((directory / 'jump-binding.json').read_text())
    if (binding['capture_sha256'] != sha(directory / 'capture.json') or
            binding['scenario'] != scenario()):
        raise ValueError('Different episode binding')
    for path, digest in binding['sources'].items():
        if sha(Path(path)) != digest:
            raise ValueError('Changed episode source: ' + path)
    with registered():
        receipt, rows = verify_capture(directory)
    if receipt['scenario_name'] != NAME or not receipt['capture_complete']:
        raise ValueError('Incomplete/wrong episode')
    selected = [r for r in rows if r['phase'] in PHASES]
    if len(selected) != 1320 or any(r['fault'] or r['input_requested'] != r['input_delivered'] for r in rows):
        raise ValueError('Missing episode frames, game fault, or undelivered input')
    samples, pairs, previous = [], [], None
    for row in selected:
        ram = bytes.fromhex(row['game_ram_hex'])
        if len(ram) != 2048:
            raise ValueError('Missing game RAM')
        sample = dict(frame=row['frame'], phase=row['phase'], room=ram[0x42],
            player_x=ram[0x388] | ram[0x390] << 8,
            working_camera=ram[0xdc] | ram[0xdd] << 8,
            committed_camera=ram[0xf6] | (ram[0x3d] & 1) << 8,
            game_tick=ram[0x10b], native=row.get('native'))
        samples.append(sample)
        # Keep all room samples in RAM report. Pixel ROI is only qualified for
        # room zero, post-fade active gameplay, not shops/transitions.
        eligible = (ram[0x42] == 0 and ram[0x100] == 0xc0 and not ram[0x107] & 128
                    and not ram[0x3e] & 0x82 and not ram[0x3f] & 0x20 and ram[0x692] == 4
                    and not row.get('native', {}).get('transition_state', 0))
        pixels = np.array(Image.open(directory / row['frame_image']).convert('RGB'))
        x0, y0, x1, y1 = ROI
        strip = pixels[y0:y1, x0:x1]
        if previous and eligible and previous[1] and previous[0]['phase'] == sample['phase']:
            pairs.append(dict(frame=sample['frame'], **displacement(previous[2], strip)))
        else:
            pairs.append(dict(frame=sample['frame'], accepted=False, reason='boundary or ineligible scenery'))
        previous = sample, eligible, strip
    phase_results = {}
    for phase in PHASES:
        subset = [s for s in samples if s['phase'] == phase]
        phase_pairs = [p for p in pairs if p['frame'] in {s['frame'] for s in subset}]
        phase_results[phase] = dict(frames=len(subset), rooms=dict(Counter(s['room'] for s in subset)),
            ram={f: changes(subset, f) for f in ('player_x', 'working_camera', 'committed_camera')},
            scenery=picture_changes(subset, phase_pairs),
            rejected_pairs=[p for p in phase_pairs if not p['accepted']])
    return receipt, dict(phases=phase_results, samples=samples, picture_pairs=pairs), binding


def audit(nes, snes, out):
    data, receipts, sources = {}, {}, {}
    for system, directory in [('nes', nes), ('snes', snes)]:
        receipt, result, binding = load(directory)
        if receipt['system'] != system:
            raise ValueError('Wrong system')
        data[system], receipts[system] = result, receipt
        sources.update(binding['sources'])
        for p in (directory / 'jump-binding.json', directory / 'capture.json'):
            sources[str(p)] = sha(p)
    if (receipts['nes']['scenario_sha256'] != receipts['snes']['scenario_sha256'] or
            receipts['nes']['rom_sha256'] != receipts['snes']['templates']['menu']['source_rom']):
        raise ValueError('Different scenario or base game')
    for p in map(Path, (__file__, 'tools/audit_physical_camera.py', 'tools/benchmark_report.py')):
        sources[str(p)] = sha(p)
    report = dict(**data, sources=sources, roi=ROI, physical_issue_resolved=False,
        release_ready=False, scope=__doc__ + ' Identical logical input schedule, independent '
        'encounters; not equal-work or physical-event reproduction. Every episode RAM sample '
        'retained. Pixel matching is restricted to the fixed school-roof band with all '
        'boundaries, transitions and ambiguous pairs reported. RAM writes can straddle a '
        'frame boundary without delaying displayed motion. No loop-speed or pop-free gate.')
    out.mkdir(parents=True, exist_ok=False)
    cards, artifacts = [], {}
    for system, directory in [('nes', nes), ('snes', snes)]:
        cards.append(f'<h2>{system.upper()}</h2>')
        compact = {phase: dict(rooms=value['rooms'],
            camera_holds=value['ram']['committed_camera']['histogram'],
            picture_holds=value['scenery']['histogram'],
            short_picture_holds=value['scenery']['short_irregular'],
            rejected_picture_pairs=len(value['rejected_pairs'])) for phase, value in data[system]['phases'].items()}
        cards.append('<pre>' + html.escape(json.dumps(compact, indent=2)) + '</pre>')
        irregular = data[system]['phases']['jump_right']['scenery']['short_irregular']
        anchors = [h['next_change'] for h in irregular] or [receipts[system]['segments'][-3]['start_frame'] + 480]
        # Unmodified source PNGs around every short picture irregularity;
        # otherwise a preselected middle-of-right-phase checkpoint.
        for anchor in anchors:
            cards.append('<div class="frames">')
            for frame in range(anchor-3, anchor+3):
                name = f'{system}-{frame:05d}.png'
                shutil.copyfile(directory / 'frames' / f'frame-{frame:05d}.png', out / name)
                artifacts[name] = sha(out / name)
                cards.append(f'<figure><img src="{name}"><figcaption>{system} frame {frame}</figcaption></figure>')
            cards.append('</div>')
    report['artifacts'] = artifacts
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    (out / 'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Matched jump scrolling</title>'
        '<style>body{background:#101821;color:#eef;font:16px system-ui;margin:25px}a{color:#9df}'
        '.frames{display:flex;flex-wrap:wrap}figure{margin:8px}img{width:256px;image-rendering:pixelated}</style>'
        '<h1>Matched jumping: player movement versus camera</h1><p>' + html.escape(report['scope']) +
        '</p><p><a href="report.json">Complete RAM, pixel-pair observations and source bindings</a></p>' + ''.join(cards))
    print(json.dumps({s: {p: dict(camera=v['ram']['committed_camera']['histogram'],
        picture=v['scenery']['histogram'], short=v['scenery']['short_irregular'])
        for p, v in data[s]['phases'].items()} for s in data}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('nes', 'snes', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    audit(**vars(parser.parse_args()))
