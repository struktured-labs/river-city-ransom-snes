"""Retain every cross-ROM image/state difference; diagnose without waiving it."""
import argparse
from collections import Counter
import hashlib
import html
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha, verify_capture
from tools.capture_combat_instructions import equivalent
from tools.capture_video_pipeline_state import REGIONS
from tools.frame_audit import verify_frame


def pixels(a, b, bg_a, bg_b, flags_a, flags_b):
    if (a.shape != b.shape or a.ndim != 3 or a.shape[1:] != (256, 3)
            or bg_a.shape != (240, 256, 3) or bg_b.shape != bg_a.shape
            or len(flags_a) != 240 or len(flags_b) != 240
            or any(x not in (0, 1) for x in (*flags_a, *flags_b))):
        raise ValueError('Invalid primary/background geometry or coverage')
    height = a.shape[0]
    if height > 240:
        raise ValueError('Primary taller than background coverage')
    changed = np.any(a != b, axis=2)
    valid = np.array([bool(x and y) for x, y in zip(flags_a, flags_b)])[:height]
    bg_changed = np.any(bg_a[:height] != bg_b[:height], axis=2) & valid[:, None]
    ys, xs = np.where(changed)
    return dict(changed_pixels=int(changed.sum()),
        bbox=[int(xs.min()), int(ys.min()), int(xs.max())+1, int(ys.max())+1] if len(xs) else None,
        changed_row_counts={str(i): int(row.sum()) for i, row in enumerate(changed) if row.any()},
        unsupported_background_lines=np.where(~valid)[0].tolist(),
        supported_background_changed_pixels=int(bg_changed.sum()),
        primary_changed_background_equal=int((changed & valid[:, None] & ~bg_changed).sum()),
        primary_changed_background_changed=int((changed & bg_changed).sum()),
        primary_changed_background_unsupported=int((changed & ~valid[:, None]).sum()))


def load(root):
    binding = bound_report(root/'video-stages-capture.json')
    receipt, rows = verify_capture(root)
    normal = Path(binding['control'])
    baseline, plain = verify_capture(normal)
    equivalent(receipt, [{k: v for k, v in r.items() if k != 'background'} for r in rows], baseline, plain)
    stages = json.loads((root/'video-stages.json').read_text())
    if not binding['observer_neutral'] or len(stages) != len(rows):
        raise ValueError('Missing neutral state coverage')
    for s, r in zip(stages, rows):
        if s['frame'] != r['frame'] or s['game_ram_sha256'] != hashlib.sha256(bytes.fromhex(r['game_ram_hex'])).hexdigest():
            raise ValueError('Unaligned video state')
        if any(len(bytes.fromhex(s[k])) != size for k, (_, size) in REGIONS.items()):
            raise ValueError('Truncated video state')
    return binding, receipt, rows, stages


def audit(parent, trial, out):
    if out.exists():
        raise ValueError('Fresh report required')
    before, after = load(parent), load(trial)
    if before[1]['core_sha256'] != after[1]['core_sha256'] or len(before[2]) != len(after[2]):
        raise ValueError('Different cores/frame coverage')
    sources = dict(before[0]['sources'], **after[0]['sources'])
    changes, ram_changes, stage_changes = [], [], []
    addresses, counts = Counter(), Counter()
    for a, b, sa, sb in zip(before[2], after[2], before[3], after[3]):
        if any(a[k] != b[k] for k in ('frame', 'phase', 'input_requested', 'input_delivered')):
            raise ValueError('Different frame/phase/input schedule')
        fields = [k for k in (*REGIONS, 'palette') if sa[k] != sb[k]]
        if fields:
            stage_changes.append(dict(frame=a['frame'], fields=fields)); counts.update(fields)
        ram_a, ram_b = bytes.fromhex(a['game_ram_hex']), bytes.fromhex(b['game_ram_hex'])
        delta = [[i, x, y] for i, (x, y) in enumerate(zip(ram_a, ram_b)) if x != y]
        if delta:
            ram_changes.append(dict(frame=a['frame'], bytes=delta)); addresses.update(x[0] for x in delta)
        if a['video_sha256'] == b['video_sha256']:
            continue
        primary, backgrounds, validity = [], [], []
        for root, row in ((parent, a), (trial, b)):
            path = verify_frame(root, row); sources[str(path)] = sha(path)
            primary.append(np.asarray(Image.open(path).convert('RGB')))
            path = root/row['background']['image']; sources[str(path)] = sha(path)
            backgrounds.append(np.asarray(Image.open(path).convert('RGB')))
            validity.append(bytes.fromhex(row['background']['valid_lines']))
        measurement = pixels(*primary, *backgrounds, *validity)
        nearby = [offset for offset in range(-3, 4)
                  if 0 <= a['frame']-1+offset < len(before[2]) and
                  before[2][a['frame']-1+offset]['video_sha256'] == b['video_sha256']]
        changes.append(dict(frame=a['frame'], phase=a['phase'], **measurement,
            equal_parent_frame_offsets=nearby, different_end_frame_stages=fields,
            native_context={k: [a['native'][k], b['native'][k]] for k in
                ('task', 'transition_state', 'logical_camera_x', 'hdma_street_scroll_x',
                 'producer_row', 'consumer_row', 'publish_count')}))
    out.mkdir()
    # Highest pixel count in each phase, ordered by severity; no shift or crop.
    chosen = {}
    for row in sorted(changes, key=lambda x: (-x['changed_pixels'], x['frame'])):
        chosen.setdefault(row['phase'], row)
    selected = list(chosen.values())[:8]
    cards = []
    for row in selected:
        frame = row['frame']
        cards.append(f'<h2>Frame {frame} · {html.escape(row["phase"])} · {row["changed_pixels"]} changed pixels</h2><div class="pair">')
        for label, root, data in (('parent', parent, before), ('trial', trial, after)):
            name = f'{frame}-{label}.png'
            shutil.copyfile(verify_frame(root, data[2][frame-1]), out/name)
            cards.append(f'<figure><img src="{name}"><figcaption>{label}</figcaption></figure>')
        cards.append('</div>')
    totals = {k: sum(r[k] for r in changes) for k in ('changed_pixels',
        'primary_changed_background_equal', 'primary_changed_background_changed',
        'primary_changed_background_unsupported')}
    report = dict(parent_rom_sha256=before[1]['rom_sha256'], trial_rom_sha256=after[1]['rom_sha256'],
        frames=len(before[2]), observer_neutral=True, changed_frames=len(changes), totals=totals,
        changes=changes, game_ram_changes=ram_changes, stage_changes=stage_changes,
        stage_different_frame_counts=dict(counts),
        ram_different_frame_counts={f'{k:04x}': v for k, v in sorted(addresses.items())},
        selected_frames=[r['frame'] for r in selected], release_ready=False,
        scope='All primary differences retained at original frame numbers. Background support is '
              'reported explicitly; unsupported pixels are not assumed equal. Equal background '
              'under a changed primary pixel narrows the difference to non-background composition, '
              'not necessarily OAM alone. WRAM stages are end-of-frame snapshots, not atomic '
              'publication events or physical OAM/CGRAM readback. Nearby-frame matches are '
              'diagnostic only: no timing realignment or equivalence waiver.')
    for p in (Path(__file__), Path('tests/test_video_stage_differences.py'),
              Path('tools/frame_audit.py'), parent/'video-stages-capture.json', trial/'video-stages-capture.json'):
        sources[str(p)] = sha(p)
    report['sources'] = sources
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Cross-ROM video differences</title>'
        '<style>body{background:#111a26;color:#eef;font:17px system-ui;max-width:1150px;margin:30px auto}'
        'a{color:#8df}.pair{display:flex}figure{margin:8px;flex:1}img{width:100%;image-rendering:pixelated}</style>'
        f'<h1>{len(changes)} changed frames: all retained</h1><p>{html.escape(report["scope"])}</p>'
        '<p>Gallery: largest pixel difference per phase, first eight phases ranked by severity.</p>'
        '<p><a href="report.json">Every changed frame, RAM byte, stage, coverage gap and source binding</a></p>'+''.join(cards))
    report['artifacts'] = {p.name: sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(changed_frames=len(changes), totals=totals, stage_counts=dict(counts))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'trial', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    audit(**vars(p.parse_args()))
