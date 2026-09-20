"""Audit logical-camera to rendered-scroll publication with exact frame images."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

try:
    from .benchmark_report import verify_capture, sha
except ImportError:
    from benchmark_report import verify_capture, sha


REGION = (0, 32, 256, 112)
BACKGROUND_REGION = (0, 32, 256, 80)


def game_state(row):
    raw = bytes.fromhex(row.get('game_ram_hex', ''))
    if len(raw) != 2048:
        raise ValueError('Every frame must retain the original 2 KiB game RAM')
    return dict(camera=int.from_bytes(raw[0xDC:0xDE], 'little'),
                scroll=raw[0xF6] | ((raw[0x3D] & 1) << 8), room=raw[0x42])


def select_frames(reference, candidate, target, room):
    ref = [(r, game_state(r)) for r in reference]
    cand = [(r, game_state(r)) for r in candidate]
    ref = [(r, s) for r, s in ref if s['room'] == room and s['camera'] == target]
    cand = [(r, s) for r, s in cand if s['room'] == room and s['camera'] == target]
    if not ref or not cand:
        raise ValueError(f'Missing camera target {target} in room {room}')
    first = cand[0][0]
    native = first.get('native', {})
    if native.get('logical_camera_x') != target:
        raise ValueError('Native logical-camera telemetry disagrees with game RAM')
    settled = next((r for r, _ in cand
                    if r['frame'] >= first['frame']
                    and r.get('native', {}).get('hdma_street_scroll_x') == target), None)
    if settled is None:
        raise ValueError(f'Camera target {target} was never published')
    return ref[0][0], first, settled


def stable_target(rows, target, room):
    """Return the second consecutive logical sample, never an image-selected row."""
    previous = None
    for row in rows:
        state = game_state(row)
        if state['room'] == room and state['camera'] == target:
            if previous is not None and row['frame'] == previous['frame'] + 1:
                return row
            previous = row
        else:
            previous = None
    raise ValueError(f'Camera target {target} in room {room} never stabilized for two frames')


def rgb555(path):
    return np.asarray(Image.open(path).convert('RGB'), dtype=np.uint8) >> 3


def mismatch(reference, candidate, region=REGION):
    x0, y0, x1, y1 = region
    a, b = rgb555(reference)[y0:y1, x0:x1], rgb555(candidate)[y0:y1, x0:x1]
    if a.shape != b.shape or a.shape != (y1-y0, x1-x0, 3):
        raise ValueError('Invalid comparison image dimensions')
    mask = np.any(a != b, axis=2)
    return int(mask.sum()), mask


def frame_path(root, row):
    relative = row.get('frame_image')
    if not relative or sha(root/relative) != row.get('frame_image_sha256'):
        raise ValueError('Missing or hash-mismatched exact frame image')
    return root/relative


def collage(paths, mask, out, labels):
    images = [Image.open(p).convert('RGB') for p in paths]
    heat = np.zeros((REGION[3]-REGION[1], REGION[2]-REGION[0], 3), dtype=np.uint8)
    heat[mask] = (255, 48, 48)
    heat = Image.fromarray(heat).resize((512, 160), Image.Resampling.NEAREST)
    panels = [im.resize((512, 448), Image.Resampling.NEAREST) for im in images] + [heat]
    canvas = Image.new('RGB', (512*4, 490), (12, 18, 28))
    draw = ImageDraw.Draw(canvas)
    for index, (panel, label) in enumerate(zip(panels, labels)):
        x = index*512
        canvas.paste(panel, (x, 42 if index < 3 else 186))
        draw.text((x+12, 12), label, fill=(235, 242, 255))
    canvas.save(out)


def audit(reference, candidate, targets, room, out):
    verified = [verify_capture(root) for root in (reference, candidate)]
    for system, (receipt, rows) in zip(('nes', 'snes'), verified):
        if (receipt['system'] != system or not receipt['capture_complete']
                or receipt['scenario_name'] != 'traversal-shop-exit'
                or not receipt.get('frame_images') or any(r['fault'] for r in rows)):
            raise ValueError('Need complete exact-frame shop-exit captures')
    if verified[0][0]['scenario_sha256'] != verified[1][0]['scenario_sha256']:
        raise ValueError('Input scenarios differ')
    out.mkdir(parents=True, exist_ok=False)
    records = []
    cards = []
    for target in targets:
        ref_first, first, _ = select_frames(
            verified[0][1], verified[1][1], target, room)
        ref = stable_target(verified[0][1], target, room)
        settled = stable_target(verified[1][1], target, room)
        if (ref['frame'] < ref_first['frame'] or settled['frame'] < first['frame']
                or settled.get('native', {}).get('hdma_street_scroll_x') != target):
            raise ValueError('Stable target is not backed by matching published scroll')
        paths = [frame_path(reference, ref), frame_path(candidate, first),
                 frame_path(candidate, settled)]
        first_diff, first_mask = mismatch(paths[0], paths[1])
        settled_diff, _ = mismatch(paths[0], paths[2])
        first_background_diff, _ = mismatch(paths[0], paths[1], BACKGROUND_REGION)
        settled_background_diff, _ = mismatch(paths[0], paths[2], BACKGROUND_REGION)
        name = f'camera-{target:03d}-collage.png'
        collage(paths, first_mask, out/name,
                [f'NES stable target {target} / frame {ref["frame"]}',
                 f'SNES first logical hit / frame {first["frame"]}',
                 f'SNES stable target / frame {settled["frame"]}',
                 'First-hit RGB555 differences'])
        published = first['native']['hdma_street_scroll_x']
        record = dict(target=target, room=room,
                      reference_first_logical_frame=ref_first['frame'],
                      reference_stable_frame=ref['frame'], first_logical_frame=first['frame'],
                      settled_frame=settled['frame'], first_published_scroll=published,
                      publication_delay_frames=settled['frame']-first['frame'],
                      reference_settle_frames=ref['frame']-ref_first['frame'],
                      first_mismatch_pixels=first_diff,
                      settled_mismatch_pixels=settled_diff,
                      first_background_mismatch_pixels=first_background_diff,
                      settled_background_mismatch_pixels=settled_background_diff,
                      pixels_compared=(REGION[2]-REGION[0])*(REGION[3]-REGION[1]),
                      background_pixels_compared=(BACKGROUND_REGION[2]-BACKGROUND_REGION[0])*(BACKGROUND_REGION[3]-BACKGROUND_REGION[1]),
                      same_frame=published == target,
                      settled_background_exact=settled_background_diff == 0,
                      collage=name)
        records.append(record)
        cards.append(f'<article><h2>Camera {target}</h2><img src="{name}">' 
                     f'<p>First logical hit publishes {published}: {first_diff} differing pixels. '
                     f'After {record["publication_delay_frames"]} frame: {settled_diff} in the full diagnostic strip, '
                     f'{settled_background_diff} in the fixed background band.</p></article>')
    same_frame = all(r['same_frame'] for r in records)
    settled_background_exact = all(r['settled_background_exact'] for r in records)
    no_slower_settle = all(r['publication_delay_frames'] <= r['reference_settle_frames']
                           for r in records)
    report = dict(schema='rcr-scroll-publication-audit-v3',
                  passed=same_frame and settled_background_exact and no_slower_settle,
                  release_ready=False, room=room, region=list(REGION),
                  background_region=list(BACKGROUND_REGION),
                  gates=dict(same_frame_publication=same_frame,
                             stable_background_exact=settled_background_exact,
                             stable_render_no_slower_than_nes=no_slower_settle),
                  checkpoints=records,
                  capture_sha256=[sha(root/'capture.json') for root in (reference, candidate)],
                  timeline_sha256=[sha(root/'timeline.json') for root in (reference, candidate)],
                  scope=('First logical-camera publication plus the deterministic second consecutive logical-camera sample at explicit targets. '
                         'The first-frame and larger actor-bearing strip differences are retained; the fixed top-of-playfield RGB555 background band must match exactly and settle no slower than NES. '
                         'The actor plane is covered separately by the CHR-bank and exhaustive staged-OAM audits. No image alignment, dynamic mask or image-selected frame.'))
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>RCR scroll publication audit</title>'
        '<style>body{background:#0c121c;color:#eef5ff;font:16px system-ui;max-width:2100px;margin:auto;padding:24px}'
        'img{width:100%;image-rendering:pixelated;border:1px solid #52657d}article{margin:36px 0}</style>'
        '<h1>Logical camera → rendered HDMA scroll</h1><p>This is a fail-closed cadence audit. '
        'The third panel is the deterministic second consecutive logical-camera frame on both systems; it is never selected by image similarity. '
        'The first-frame and full actor-bearing strip differences remain visible. The fixed y=32..79 background band must match exactly, '
        'and candidate settling may not take longer than NES. This is a fixed region, not an actor-derived mask.</p>'
        '<p><a href="report.json">Machine-readable measurements and hashes</a></p>'+''.join(cards))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--target', type=int, action='append', required=True)
    parser.add_argument('--room', type=int, default=2)
    parser.add_argument('--require-pass', action='store_true')
    args = parser.parse_args()
    result = audit(args.reference, args.candidate, args.target, args.room, args.out)
    print(json.dumps(result, indent=2))
    raise SystemExit(1 if args.require_pass and not result['passed'] else 0)
