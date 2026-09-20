"""Report recorder repair and remaining observer effects without certifying hardware."""
import argparse
from collections import Counter
import html
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image

from tools.audit_camera_log_controls import differences
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha, verify_capture
from tools.review_candidate_combat import native_clip

CAMERA_FIELDS = ('scroll_x', 'logical_camera_x', 'hdma_street_scroll_x',
                 'game_nmi_ticks_010b', 'deferred_game_nmi_fallback')


def compare(left, right):
    result = differences(left, right)
    result['video_differences'] = [a['frame'] for a, b in zip(left, right)
                                  if a['video_sha256'] != b['video_sha256']]
    result['camera_field_differences'] = {
        k: [a['frame'] for a, b in zip(left, right) if a['native'][k] != b['native'][k]]
        for k in CAMERA_FIELDS}
    result['input_and_phase_exact'] = len(left) == len(right) and all(
        all(a[k] == b[k] for k in ('phase', 'input_requested', 'input_delivered'))
        for a, b in zip(left, right))
    result['camera_fields_exact'] = len(left) == len(right) and not any(
        result['camera_field_differences'].values())
    return result


def audit(manifest, out):
    if out.exists():
        raise ValueError('Fresh output required')
    spec = json.loads(manifest.read_text())
    paths = (manifest, Path(__file__), Path('tools/audit_camera_log_controls.py'),
             Path('tools/audit_main_display_latency.py'), Path('tools/benchmark_report.py'),
             Path('tools/review_candidate_combat.py'), Path('tests/test_wait_camera_review.py'))
    sources = {str(p): sha(p) for p in paths}
    cache = {}
    for name in {v for pair in spec['pairs'].values() for v in pair.values()}:
        folder = Path(name)
        receipt, rows = verify_capture(folder)
        for filename in ('capture.json', 'timeline.json', 'audio.wav'):
            p = folder/filename
            sources[str(p)] = sha(p)
        if (folder/'logger-report.json').exists():
            p = folder/'logger-report.json'
            proof = bound_report(p)
            sources[str(p)] = sha(p)
            sources.update(proof['sources'])
            candidates = [Path(p) for p in proof['sources'] if p.endswith('/manifest.json')]
            if len(candidates) != 1:
                raise ValueError('Ambiguous diagnostic manifest')
            meta = json.loads(candidates[0].read_text())
            # Authenticate the diagnostic patch chain explicitly, not merely
            # the capture receipt's flat manifest hash. Historical production
            # sources are not claimed reproducible from today's worktree.
            for key in ('diagnostic_camera_log', 'camera_idle_log',
                        'idle_camera_branch_repair', 'camera_wait_log'):
                for p, h in meta.get(key, {}).get('sources', {}).items():
                    if sha(Path(p)) != h:
                        raise ValueError('Changed diagnostic dependency: '+p)
                    sources[p] = h
        cache[name] = (receipt, rows)
    out.mkdir(parents=True)
    results = {}
    cards = []
    for name, pair in spec['pairs'].items():
        base, left = cache[pair['baseline']]
        trial, right = cache[pair['trial']]
        if any(base[k] != trial[k] for k in ('core_sha256', 'scenario_sha256')):
            raise ValueError('Different replay/core')
        result = compare(left, right)
        result.update(complete=trial['capture_complete'], frames=len(right),
                      baseline_complete=base['capture_complete'],
                      fault_frames=sum(bool(r['fault']) for r in right),
                      pcm_exact=base['audio_sha256'] == trial['audio_sha256'])
        result['neutral'] = result['timeline_exact'] and result['pcm_exact'] and result['complete']
        pixel_changes = []
        for frame in result['video_differences']:
            pictures = []
            for label, rows in (('baseline', left), ('trial', right)):
                p = Path(pair[label])/f'frames/frame-{frame:05d}.png'
                if sha(p) != rows[frame-1]['frame_image_sha256']:
                    raise ValueError('Changed frame image')
                sources[str(p)] = sha(p)
                pictures.append(np.asarray(Image.open(p).convert('RGB')))
            delta = np.any(pictures[0] != pictures[1], axis=2)
            yy, xx = np.where(delta)
            pixel_changes.append(dict(frame=frame, changed_pixels=len(xx),
                bounds=[int(xx.min()), int(yy.min()), int(xx.max()), int(yy.max())],
                top_strip_changed=int(delta[32:56].sum())))
        result['pixel_changes'] = pixel_changes
        result['top_strip_exact'] = len(left) == len(right) and not any(
            r['top_strip_changed'] for r in pixel_changes)
        # Explicitly retain stage/tick/camera versus full-image/PCM distinctions.
        results[name] = result
        cards.append('<h2>'+html.escape(name)+'</h2><p>'+html.escape(json.dumps({
            k: result[k] for k in ('frames', 'complete', 'fault_frames', 'neutral',
                                   'camera_fields_exact', 'top_strip_exact', 'pcm_exact')}))+'</p>')
        selected = result['video_differences'][:3]
        for frame in selected:
            cards.append(f'<p>Frame {frame}, baseline then diagnostic</p><div class="pair">')
            for label in ('baseline', 'trial'):
                source = Path(pair[label])/f'frames/frame-{frame:05d}.png'
                target = f'{name}-{label}-{frame}.png'
                shutil.copyfile(source, out/target)
                cards.append(f'<img src="{target}">')
            cards.append('</div>')
        audio_frame = result['first_difference']['audio']
        if audio_frame is not None:
            for label, rows in (('baseline', left), ('trial', right)):
                start = max(0, audio_frame-31)
                end = min(len(rows)-1, audio_frame+90)
                target = f'{name}-{label}.wav'
                native_clip(Path(pair[label])/'audio.wav', out/target,
                            rows[start]['audio_start_sample'], rows[end]['audio_start_sample'])
                cards.append(f'<p>{label}, native PCM around first differing audio frame</p>'
                             f'<audio controls preload="none" src="{target}"></audio>')
    trace_proof = Path(spec['failure_trace'])/'failure-observer.json'
    proof = bound_report(trace_proof)
    if not proof['observer_neutral'] or proof['capture_complete']:
        raise ValueError('Need exact replay of original failing cartridge')
    sources.update(proof['sources'])
    sources[str(trace_proof)] = sha(trace_proof)
    import csv
    with Path(proof['trace']).open() as stream:
        trace = list(csv.reader(stream))
    event = next((dict(before=a, after=b) for a,b in zip(trace,trace[1:])
                  if a[4] == 'c0e00c' and b[4] == 'c0df8e'), None)
    if event is None:
        raise ValueError('Missing actual branch into padding')
    scope = ('Offline recorder studies, not gameplay fixes. All original timeline/RAM/PCM differences '
             'remain failures of full neutrality. Camera fields are frame-end shadows, not actual '
             'scanline readback. Fixed y32:56 image strip is only a limited scenery check, not every '
             'background row. Incomplete trials are retained. No hardware deployment, original-speed '
             'or pop-free certification. Diagnostic source dependencies are checked; inherited '
             'historical production source reproducibility is not asserted.')
    report = dict(results=results, faulty_branch=event, sources=sources, scope=scope,
                  physical_deployed=False, release_ready=False)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Idle recorder repair</title>'
        '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}'
        'a{color:#8df}.pair{display:flex;gap:20px}.pair img{width:45%;image-rendering:pixelated}'
        'audio{width:100%}p{overflow-wrap:anywhere}</style><h1>Recorder repair; observer effects retained</h1><p>'
        +html.escape(scope)+'</p>'+''.join(cards)+'<p><a href="report.json">Complete comparisons and hashes</a></p>')
    report['artifacts'] = {p.name: sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({name: {k: r[k] for k in ('frames', 'complete', 'neutral', 'camera_fields_exact',
                                               'top_strip_exact', 'pcm_exact')}
                      for name,r in results.items()}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    audit(**vars(p.parse_args()))
