"""Measure horizontal scenery motion in decoded OBS video, not core timing.

Explicit caller-supplied scenery ROI must exclude sprites/OSD. All rejected
matches and long stops are retained. OBS cadence can duplicate/drop hardware
frames, so this is not an NMI or original-speed certification.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess

import numpy as np

from tools.benchmark_report import sha


def displacement(before, after, max_shift=4):
    if before.shape != after.shape or before.ndim != 3 or before.shape[2] != 3:
        raise ValueError('Need matching RGB scenery strips')
    if before.shape[1] <= 4*max_shift or max_shift < 1:
        raise ValueError('Strip too narrow for displacement search')
    edge = 2*max_shift
    core = before[:, edge:-edge].astype(np.int16)
    # Spatial variation, not RGB channel differences in a flat cyan area.
    variation = float(np.std(core.astype(float), axis=(0, 1)).max())
    candidates = []
    for delta in range(-max_shift, max_shift+1):
        shifted = after[:, edge+delta:after.shape[1]-edge+delta].astype(np.int16)
        candidates.append((float(np.abs(core-shifted).mean()), delta))
    candidates.sort()
    error, picture_shift = candidates[0]
    margin = candidates[1][0]-error
    accepted = variation >= 10 and error <= 8 and margin >= 1
    return dict(accepted=accepted, camera_delta=-picture_shift, error=error,
                next_best_margin=margin, spatial_variation=variation)


def cadence(pairs):
    if [p['frame'] for p in pairs] != list(range(2,len(pairs)+2)):
        raise ValueError('Missing or reordered decoded frame pairs')
    holds, previous = [], None
    for pair in pairs:
        if not pair['accepted']:
            previous = None
            continue
        delta = pair['camera_delta']
        if delta == 0:
            continue
        if previous is not None and delta == previous['camera_delta']:
            holds.append(dict(first_change=previous['frame'], next_change=pair['frame'],
                frames=pair['frame']-previous['frame'], camera_delta=delta))
        previous = pair
    return dict(holds=holds, histogram=dict(Counter(h['frames'] for h in holds)),
        short_irregular=[h for h in holds if h['frames'] in (1, 3, 4)])


def analyze(strips):
    if len(strips) < 2:
        raise ValueError('Need multiple decoded frames')
    pairs = [dict(frame=i+2, **displacement(a, b))
             for i, (a, b) in enumerate(zip(strips, strips[1:]))]
    return dict(pairs=pairs, accepted_pairs=sum(p['accepted'] for p in pairs),
        rejected_pairs=[p['frame'] for p in pairs if not p['accepted']],
        camera_delta_histogram=dict(Counter(p['camera_delta'] for p in pairs if p['accepted'])),
        **cadence(pairs))


def audit(video, roi, logical_width, out):
    description = json.loads(subprocess.check_output(['ffprobe', '-v', 'error',
        '-select_streams', 'v:0', '-show_entries', 'stream=width,height,r_frame_rate,nb_frames',
        '-of', 'json', str(video)]))['streams'][0]
    x, y, width, height = roi
    if (min(x,y) < 0 or min(width,height,logical_width) <= 0 or
            x+width > description['width'] or y+height > description['height'] or
            width % logical_width):
        raise ValueError('Need a bounded integral horizontal-scale ROI')
    logical_height = max(1, height*logical_width//width)
    geometry = f'crop={width}:{height}:{x}:{y},scale={logical_width}:{logical_height}:flags=neighbor'
    raw = subprocess.check_output(['ffmpeg','-v','error','-i',str(video),'-vf',geometry,
        '-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgb24','pipe:1'])
    stride = logical_width*logical_height*3
    if len(raw) % stride or len(raw)//stride != int(description['nb_frames']):
        raise ValueError('Incomplete or duplicated decode')
    strips = np.frombuffer(raw,np.uint8).reshape(-1,logical_height,logical_width,3)
    result = analyze(strips)
    # Fixed synthetic sequence uses the same measured scenery, two-frame holds
    # and a two-logical-pixel movement. It must recover all shifts and detect
    # an inserted duplicate; this is matcher sensitivity, not core emulation.
    source = next((s for s in strips if displacement(s,s)['accepted']),None)
    if source is None:
        raise ValueError('Scenery has no identifiable spatial texture')
    fixture = np.array([np.roll(source,-2*(i//2),axis=1) for i in range(12)])
    baseline = analyze(fixture)
    duplicated = analyze(np.insert(fixture,5,fixture[4],axis=0))
    controls = dict(two_frame_fixture_recovered=baseline['histogram'] == {2:4},
        inserted_duplicate_detected=any(h['frames']==3 for h in duplicated['holds']))
    result.update(video_sha256=sha(video), video=description, roi=roi,
        logical_width=logical_width, logical_height=logical_height,
        matcher_controls=controls, decoded_frames=len(strips), speed_verified=False, release_ready=False,
        implementation_sha256=sha(Path(__file__)),
        scope='Scenery-only translational matching in encoded OBS frames. Caller-selected ROI '
              'must be visually checked for actors/overlays. Rejected matches and long stops '
              'retained; holds compare equal signed nonzero movement steps. OBS60Hz and '
              'MiSTer scanout/capture cadence are not identical clocks. A1/3-frame pattern '
              'may arise in capture, not the game. No NMI, input-latency, NES-speed, full-frame '
              'content or tear-free certification.')
    out.mkdir(parents=True,exist_ok=False)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('decoded_frames','accepted_pairs','rejected_pairs',
        'camera_delta_histogram','histogram','matcher_controls')}))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--video',required=True,type=Path)
    p.add_argument('--roi',required=True,nargs=4,type=int,metavar=('X','Y','W','H'))
    p.add_argument('--logical-width',required=True,type=int)
    p.add_argument('--out',required=True,type=Path)
    audit(**vars(p.parse_args()))
