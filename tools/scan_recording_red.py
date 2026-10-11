"""Find transient red vertical strips in a stream recording (issue #26).

Decodes a window of an OBS recording at full frame rate, crops the game area,
scales it to native 256x224 and counts saturated-red pixels per 8-px column
band. A band is flagged when its red count jumps well above both the previous
and the next frame (a one- or two-frame flicker), and flagged frames are saved.

usage: python3 -m tools.scan_recording_red VIDEO START_S DURATION_S OUT
       [--crop W:H:X:Y]  (default: this stream layout, 1280:836:340:30)
"""
import argparse
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

W, H = 256, 224


def frames(video, start, dur, crop):
    cmd = ['ffmpeg', '-v', 'error', '-ss', str(start), '-t', str(dur), '-i', str(video),
           '-vf', f'crop={crop},scale={W}:{H}:flags=neighbor', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    n = W * H * 3
    while True:
        buf = p.stdout.read(n)
        if len(buf) < n:
            break
        yield np.frombuffer(buf, np.uint8).reshape(H, W, 3)
    p.wait()


def diff_bands(a, b):
    d = np.abs(a.astype(int) - b.astype(int)).sum(axis=2)[24:]   # below the HUD
    return (d > 90).reshape(H - 24, W // 4, 4).sum(axis=(0, 2))


def band_shifts(a, b, rows=8, span=3):
    """Best horizontal shift per row band of the playfield, b relative to a."""
    ga, gb = a.astype(int).sum(axis=2), b.astype(int).sum(axis=2)
    out = []
    for y in range(32, H, rows):
        ra, rb = ga[y:y + rows, span:W - span], gb[y:y + rows]
        cost = [np.abs(ra - rb[:, span + s:W - span + s]).mean() for s in range(-span, span + 1)]
        best = int(np.argmin(cost))
        flat = max(cost) - min(cost) < 6          # textureless band: no opinion
        out.append(None if flat else best - span)
    return out


def red_bands(img):
    r, g, b = (img[..., i].astype(int) for i in range(3))
    red = (r > 150) & (g < 90) & (b < 90)
    return red.reshape(H, W // 8, 8).sum(axis=(0, 2))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('video')
    ap.add_argument('start', type=float)
    ap.add_argument('dur', type=float)
    ap.add_argument('out', type=Path)
    ap.add_argument('--crop', default='1280:836:340:30')
    ap.add_argument('--min-jump', type=int, default=40)
    ap.add_argument('--mode', choices=('red', 'transient', 'tear'), default='red',
                    help='transient: a 4-px column band that differs from both neighbours in time')
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    hist, imgs, hits = [], [], []
    for i, img in enumerate(frames(a.video, a.start, a.dur, a.crop)):
        hist.append(red_bands(img))
        imgs.append(img)
        if len(hist) >= 3:
            prev, cur, nxt = hist[-3], hist[-2], hist[-1]
            if a.mode == 'tear':
                sh = [x for x in band_shifts(imgs[-3], imgs[-2]) if x is not None]
                vals = sorted(set(sh))
                # uniform scroll: every textured band agrees; a tear splits them
                spread = (vals[-1] - vals[0]) if len(sh) >= 6 else 0
                minority = min(sh.count(v) for v in vals) if len(vals) > 1 else 0
                jump = np.array([spread * 100 if minority >= 2 else 0])
            elif a.mode == 'transient':
                # a band that changed against both neighbours while the frames
                # either side agree there: a one-frame strip, not motion
                flash = np.minimum(diff_bands(imgs[-2], imgs[-3]), diff_bands(imgs[-2], imgs[-1]))
                jump = flash - diff_bands(imgs[-3], imgs[-1])
            else:
                jump = cur - np.maximum(prev, nxt)
            band = int(jump.argmax())
            if jump[band] >= a.min_jump:
                t = a.start + (i - 1) / 60
                name = f'hit_{t:08.2f}_band{band:02d}.png'
                Image.fromarray(np.hstack([imgs[-3], imgs[-2], imgs[-1]])).save(a.out / name)
                hits.append(dict(t=round(t, 2), band=band, x=band * (4 if a.mode == 'transient' else 8),
                                 jump=int(jump[band])))
            hist.pop(0)
            imgs.pop(0)
    (a.out / 'hits.json').write_text(json.dumps(hits, indent=1))
    print(json.dumps(dict(frames=i + 1, hits=len(hits), right_edge=[h for h in hits if h['x'] >= 232][:20]), indent=1))


if __name__ == '__main__':
    main()
