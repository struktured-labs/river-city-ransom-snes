"""Retain exact decoded pictures and timestamp/region changes around camera holds."""
import argparse
from collections import Counter
import html
import json
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image

from tools.benchmark_report import sha

REGIONS = {'game': (340, 142, 1280, 724), 'roof': (340, 160, 1280, 120),
           'actors': (340, 480, 1280, 250)}


def difference(before, after, roi):
    x, y, w, h = roi
    if before.shape != after.shape or min(x, y) < 0 or min(w, h) < 1 or y+h > before.shape[0] or x+w > before.shape[1]:
        raise ValueError('Invalid image pair/ROI')
    delta = np.abs(after[y:y+h, x:x+w].astype(np.int16)-before[y:y+h, x:x+w].astype(np.int16))
    return dict(mean_absolute_channel_difference=float(delta.mean()),
                pixels_changed_by_at_least_32=int((delta.max(axis=2) >= 32).sum()),
                pixels=w*h)


def audit(camera, video, out):
    report = json.loads(camera.read_text())
    if (report['video_sha256'] != sha(video) or report['implementation_sha256'] !=
            sha(Path('tools/audit_physical_camera.py'))):
        raise ValueError('Camera/video source changed')
    probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_frames', '-show_entries', 'frame=best_effort_timestamp_time', '-of', 'json', str(video)]))
    times = [float(r['best_effort_timestamp_time']) for r in probe['frames']]
    if len(times) != report['decoded_frames'] or any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError('Missing or unordered frame timestamps')
    if report['video']['width'] != 1920 or report['video']['height'] != 1080:
        raise ValueError('Fixed regions require verified 1920x1080 layout')
    events = report['short_irregular']
    selected = sorted({i for e in events for i in range(max(1, e['first_change']-2),
                                                       min(len(times), e['next_change']+2)+1)})
    if not selected:
        raise ValueError('No irregular holds to inspect')
    selection = '+'.join(f'eq(n\\,{i-1})' for i in selected)
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(video), '-vf', 'select='+selection,
        '-fps_mode', 'passthrough', '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1'])
    if len(raw) != len(selected)*1920*1080*3:
        raise ValueError('Incomplete frame decode')
    pictures = dict(zip(selected, np.frombuffer(raw, np.uint8).reshape(-1, 1080, 1920, 3)))
    out.mkdir(parents=True, exist_ok=False)
    artifacts, observations = {}, []
    for i, picture in pictures.items():
        name = f'frame-{i:05d}.png'
        Image.fromarray(picture).save(out / name)
        artifacts[name] = sha(out / name)
        observations.append(dict(frame=i, pts_seconds=times[i-1],
            previous_interval_ms=(times[i-1]-times[i-2])*1000 if i > 1 else None,
            differences={name: difference(pictures[i-1], picture, roi) for name, roi in REGIONS.items()}
                        if i-1 in pictures else None))
    result = dict(events=events, observations=observations, regions=REGIONS,
        pts_interval_ms_histogram=dict(Counter(round((b-a)*1000, 3) for a, b in zip(times, times[1:]))),
        sources={str(p): sha(p) for p in (Path(__file__), camera, video, Path('tools/audit_physical_camera.py'))},
        artifacts=artifacts, physical_issue_resolved=False,
        scope='Exact decoded full pictures; no image scaling, alignment or filtering in saved PNGs. '
        'HTML thumbnails only scale display. Fixed region differences retain codec noise; the 32-level '
        'threshold is a descriptive motion count, not a pass/fail gate. Uniform encoded PTS does not '
        'prove unique source frames or identify a game stall. Actor changes during a roof hold rule '
        'out an identical whole picture, not a delayed background publication.')
    (out / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
    cards = []
    for row in observations:
        cards.append(f'<figure><a href="frame-{row["frame"]:05d}.png"><img src="frame-{row["frame"]:05d}.png"></a>'
            f'<figcaption>Frame {row["frame"]}, PTS {row["pts_seconds"]:.3f}s</figcaption><pre>' +
            html.escape(json.dumps(row['differences'], indent=2)) + '</pre></figure>')
    (out / 'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Rival camera hold context</title>'
        '<style>body{background:#101821;color:#eef;font:16px system-ui;margin:24px}a{color:#9df}'
        'section{display:flex;flex-wrap:wrap}figure{width:460px;margin:8px}img{width:100%}pre{font-size:12px}</style>'
        '<h1>Rival camera holds: original pictures and timing</h1><p>' + html.escape(result['scope']) +
        '</p><p><a href="report.json">All measurements and hashes</a></p><section>' + ''.join(cards) + '</section>')
    print(json.dumps(dict(frames=selected, pts=result['pts_interval_ms_histogram'],
        observations=[r for r in observations if r['frame'] in (661, 1065, 1067)]), indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('camera', 'video', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    audit(**vars(p.parse_args()))
