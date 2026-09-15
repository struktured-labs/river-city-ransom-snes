"""Render explicitly selected, pixel-bound transition frames for human audit."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import shutil

from PIL import Image

try:
    from .benchmark_report import verify_capture, sha
except ImportError:
    from benchmark_report import verify_capture, sha


def verify_frame(root, row):
    relative = Path(row['frame_image'])
    if relative != Path('frames')/f"frame-{row['frame']:05d}.png":
        raise ValueError('Frame image path does not match frame number')
    path = root/relative
    if sha(path) != row['frame_image_sha256']:
        raise ValueError('Frame PNG hash mismatch')
    with Image.open(path) as source:
        pixels = source.convert('RGB').tobytes()
    if hashlib.sha256(pixels).hexdigest() != row['video_sha256']:
        raise ValueError('Frame pixels do not match captured video')
    return path


def audit(capture, frames, out):
    receipt, timeline = verify_capture(capture)
    if not receipt.get('frame_images'):
        raise ValueError('Capture did not retain every frame')
    if not frames or len(set(frames)) != len(frames):
        raise ValueError('Need distinct explicit frame numbers')
    selected = []
    for frame in frames:
        if not 1 <= frame <= len(timeline):
            raise ValueError('Frame outside capture')
        row = timeline[frame-1]
        path = verify_frame(capture, row)
        selected.append((row, path))
    out.mkdir(parents=True, exist_ok=False)
    cards, records = [], []
    for row, path in selected:
        shutil.copyfile(path, out/path.name)
        native = row.get('native', {})
        detail = {k: native.get(k) for k in ('ppu_mask', 'row_states', 'chr_jobs_pending', 'publish_count')}
        records.append(dict(frame=row['frame'], phase=row['phase'], image=path.name,
                            image_sha256=sha(out/path.name), native=detail))
        caption = html.escape(f"Frame {row['frame']} · {row['phase']} · {detail}")
        cards.append(f'<figure><img src="{path.name}"><figcaption>{caption}</figcaption></figure>')
    report = dict(schema='rcr-frame-audit-v1', capture_sha256=sha(capture/'capture.json'),
                  rom_sha256=receipt['rom_sha256'], frames=records,
                  scope='Explicit frame contact sheet; raw pixels verified, no automatic visual quality verdict')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Transition frame audit</title>'
        '<style>body{background:#141820;color:#eee;font:14px sans-serif}.frames{display:flex;flex-wrap:wrap}'
        'figure{margin:8px;width:256px}img{width:256px;image-rendering:pixelated}figcaption{overflow-wrap:anywhere}</style>'
        '<h1>Transition frame audit</h1><p>Explicit frame selection, no image alignment or automatic visual pass.</p>'
        '<p><a href="report.json">Frame selection, ROM and image hashes</a></p><div class="frames">'
        + ''.join(cards)+'</div>')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', required=True, type=Path)
    parser.add_argument('--frames', required=True, nargs='+', type=int)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.capture, args.frames, args.out), indent=2))
