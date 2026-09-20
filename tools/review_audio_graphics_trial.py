"""Compare neutral short audio trials, preserving audio and every visual delta."""
import argparse
from bisect import bisect_right
import csv
import json
from pathlib import Path
import shutil
import statistics
import wave
import numpy as np
from PIL import Image
from tools.audit_busy_combat import classify
from tools.audit_dsp_latency import validate_trace, raw_identity
from tools.audit_main_display_latency import bound_report
from tools.audit_sound_service_phases import pair
from tools.benchmark_report import sha, verify_capture
from tools.capture_sprite_prefix import installed_prefix


def review(before, after, out):
    if out.exists():
        raise ValueError('Fresh report required')
    sources = {}; runs = {}; timelines = {}; clips = {}
    for name, folder in [('before', before), ('after', after)]:
        proof = bound_report(folder / 'audio-prefix.json')
        if not proof['observer_neutral'] or not proof.get('post_exit_finalization'):
            raise ValueError('Need neutral, process-finalized observation')
        sources.update(proof['sources'])
        sources[str(folder / 'audio-prefix.json')] = sha(folder / 'audio-prefix.json')
        with installed_prefix('right_08'):
            receipt, rows = verify_capture(folder)
        timelines[name] = rows
        with wave.open(str(folder / 'audio.wav')) as stream:
            rate = stream.getframerate(); n = stream.getnframes()
            if rate != 32040 or stream.getnchannels() != 2 or stream.getsampwidth() != 2:
                raise ValueError('Unexpected native PCM format')
            pcm = np.frombuffer(stream.readframes(n), dtype='<i2').reshape(-1, 2)
        with open(proof['traces']['RCR_DSP_LATENCY_TRACE']) as stream:
            trace = list(csv.reader(stream))
        packets, writes, callbacks = validate_trace(trace, rows, n)
        raw_identity(np.fromfile(proof['traces']['RCR_DSP_DAC_PCM'], dtype='<i2').reshape(-1, 2), pcm)
        ready = [(int(r[1]), int(r[2])) for r in trace if r[0] == 'R' and int(r[1]) > 0]
        if [p for p, t in ready] != list(range(1, len(packets)+1)):
            raise ValueError('Missing or duplicate completed packet')
        starts = [r['audio_start_sample'] for r in rows]; stable = []; excluded = []
        for (p, t), (q, u) in zip(ready, ready[1:]):
            first = bisect_right(starts, (t+4)//32); last = bisect_right(starts, (u+4)//32)
            if not 1 <= first <= last <= len(rows):
                raise ValueError('Packet outside timeline')
            context = classify(rows[first-1:last])
            record = dict(previous_packet=p, packet=q, first_frame=first, last_frame=last,
                          gap_ms=(u-t)*1000/(32040*32), context=context)
            (stable if context['room'] is not None else excluded).append(record)
        with open(proof['traces']['RCR_MAIN_STORE_TRACE']) as stream:
            calls, intervals = pair(csv.reader(stream))
        focus = [r for r in intervals if r['current']['entry']['frame'] == 2120]
        if len(focus) != 1:
            raise ValueError('Missing targeted original-driver interval')
        local = [r['return_gap_ms'] for r in intervals if 1700 < r['current']['entry']['frame'] < 2400]
        values = [r['gap_ms'] for r in stable]
        runs[name] = dict(rom_sha256=receipt['rom_sha256'], frames=len(rows), packets=len(packets),
            driver_focus=focus[0], driver_local_range_ms=[min(local), max(local)],
            stable_completion_range_ms=[min(values), max(values)],
            stable_completion_median_ms=statistics.median(values), stable=stable, excluded=excluded,
            intervals=intervals, samples=n, peak=int(np.abs(pcm.astype(np.int32)).max()),
            clipped=int(np.count_nonzero(np.abs(pcm.astype(np.int32)) >= 32767)))
        # Identical unnormalized native sample range, no timing alignment.
        clips[name] = pcm[34*rate:37*rate].tobytes()
    a = timelines['before']; b = timelines['after']
    if len(a) != len(b):
        raise ValueError('Different prefix lengths; retain separately before comparison')
    differences = {}
    for key in ('probe_052b', 'input_requested', 'input_delivered', 'video_sha256'):
        differences[key] = [x['frame'] for x, y in zip(a, b) if x[key] != y[key]]
    differences['logical_camera'] = [x['frame'] for x, y in zip(a, b)
                                    if x['native']['logical_camera_x'] != y['native']['logical_camera_x']]
    changed = differences['video_sha256']; visual = []
    out.mkdir(parents=True)
    for frame in changed:
        images = []
        for name, folder in [('before', before), ('after', after)]:
            path = folder / timelines[name][frame-1]['frame_image']
            sources[str(path)] = sha(path)
            shutil.copyfile(path, out / f'{name}-{frame}.png')
            images.append(np.asarray(Image.open(path).convert('RGB')))
        yy, xx = np.where(np.any(images[0] != images[1], axis=2))
        visual.append(dict(frame=frame, changed_pixels=len(xx),
                           bbox=[int(xx.min()), int(yy.min()), int(xx.max()), int(yy.max())]))
    for name, payload in clips.items():
        with wave.open(str(out / f'{name}.wav'), 'wb') as stream:
            stream.setnchannels(2); stream.setsampwidth(2); stream.setframerate(32040); stream.writeframes(payload)
    for path in (Path(__file__), Path('tools/audit_sound_service_phases.py'),
                 Path('tools/audit_dsp_latency.py'), Path('tools/audit_busy_combat.py')):
        sources[str(path)] = sha(path)
    report = dict(runs=runs, differences=differences, visual=visual, sources=sources,
        release_ready=False, visual_changes_resolved=False, pop_free_verified=False,
        scope=__doc__ + ' Stable/excluded packet intervals all retained. CPU-frame local region '
        '1701–2399 is diagnostic, not matched-NES workload. Clips use samples1089360–1185479 '
        '(34–37 seconds), untouched native32040Hz stereo PCM. No source waveform equivalence claimed.')
    body = '<!doctype html><meta charset="utf-8"><title>Audio/graphics experiment</title><style>body{background:#091016;color:#e8f2f7;font:17px/1.6 system-ui;max-width:1100px;margin:30px auto;padding:20px}a{color:#6de5e8}.pair{display:flex;gap:12px}figure{margin:0;flex:1}img{width:100%;image-rendering:pixelated}td{padding:12px;border-bottom:1px solid #345}</style><h1>Audio/graphics experiment: measurements, not release approval</h1><p>Exact ROM hashes are listed below. No hardware deployment; not release-ready.</p><table>'
    for name, r in runs.items():
        body += f'<p>{name}: <code>{r["rom_sha256"]}</code></p>'
        body += f'<tr><td>{name}</td><td>Target driver return gap {r["driver_focus"]["return_gap_ms"]:.3f}ms</td><td>Stable sound-packet spacing {r["stable_completion_range_ms"][0]:.3f}–{r["stable_completion_range_ms"][1]:.3f}ms</td></tr>'
    body += f'</table><p>Game counter, input and camera difference counts: {len(differences["probe_052b"])}, {len(differences["input_delivered"])}, {len(differences["logical_camera"])}. {len(changed)} changed pictures are retained below; they are not waived.</p><p>Native audio, same34–37s sample range. No gain changes, filtering or time alignment.</p>'
    for name in runs:
        body += f'<p>{name}: <audio controls preload="none" src="{name}.wav"></audio></p>'
    body += '<p><a href="report.json">Complete intervals, exclusions, differences and hashes</a> · <a href="../progress-3728/">Project progress</a> · <a href="https://github.com/struktured-labs/river-city-ransom-snes/issues/6">Audio issue #6</a></p>'
    for r in visual:
        body += f'<h2>Frame {r["frame"]}: {r["changed_pixels"]} changed pixels</h2><div class="pair">'
        for name in runs:
            body += f'<figure><img src="{name}-{r["frame"]}.png" alt="{name} frame {r["frame"]}"><figcaption>{name}</figcaption></figure>'
        body += '</div>'
    (out / 'index.html').write_text(body)
    report['artifacts'] = {p.name: sha(p) for p in out.iterdir() if p.is_file()}
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(changed_frames=len(changed), runs={k: {field: v[field] for field in
        ('driver_local_range_ms', 'stable_completion_range_ms', 'packets', 'clipped')} for k, v in runs.items()})))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('before', 'after', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    review(**vars(parser.parse_args()))

