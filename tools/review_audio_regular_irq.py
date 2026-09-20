"""Camera pre-service ablation: exact event timing and all changed pictures."""
import argparse
import csv
import html
import json
from pathlib import Path
import shutil
from tools.benchmark_report import sha, verify_capture
from tools.review_command_priority import bound


def events(rows):
    if any(int(b[3]) <= int(a[3]) for a, b in zip(rows, rows[1:])):
        raise ValueError('Nonmonotonic CPU trace')
    names = {0x325c: 'camera_entry', 0x325f: 'camera_continuation',
             0x33a6: 'camera_restore_policy', 0xfa54: 'sound_entry', 0xfa64: 'sound_return'}
    result = []
    for row in rows:
        pc = int(row[4], 16)
        if (pc & 0xffff) in names:
            result.append(dict(event=names[pc & 0xffff], frame=int(row[0]), line=int(row[1]),
                               cycle=int(row[2]), clock=int(row[3]), pc=row[4]))
    for frame in range(8530, 8534):
        pair = [r for r in result if r['frame'] == frame and r['event'].startswith('sound_')]
        if [r['event'] for r in pair] != ['sound_entry', 'sound_return']:
            raise ValueError('Missing, extra or censored sound invocation')
    return result


def review(out):
    if out.exists():
        raise ValueError('Fresh report required')
    roots = [Path('build/early-oam-live-half-full-3957'), Path('build/audio-regular-irq-full-4035')]
    runs = [verify_capture(p) for p in roots]
    a, b = [r[1] for r in runs]
    if len(a) != len(b):
        raise ValueError('Different route length')
    changed = {k: [x['frame'] for x, y in zip(a, b) if x[k] != y[k]] for k in
               ('video_sha256', 'game_ram_hex', 'nmi_counter', 'input_requested', 'input_delivered', 'fault')}
    changed.update({k: [x['frame'] for x, y in zip(a, b) if x['native'][k] != y['native'][k]]
                    for k in ('logical_camera_x', 'game_nmi_ticks_010b')})
    paths = [Path(__file__), Path('tests/test_audio_regular_irq_review.py')]
    cpu = []
    for root in ('build/command-gap-parent-cpu-4003', 'build/audio-regular-irq-cpu-4038'):
        proof = Path(root) / 'service-instructions.json'
        info = bound(proof)
        if not info['observer_neutral']:
            raise ValueError('Unqualified observer')
        verify_capture(Path(root))
        trace = Path(info['trace'])
        cpu.append(events(list(csv.reader(trace.open()))))
        paths.extend((proof, trace))
    audio = []
    for root in ('build/early-oam-live-half-audio-review-3962', 'build/audio-regular-irq-audio-review-4037'):
        proof = Path(root) / 'report.json'
        audio.append(bound(proof)['summary'])
        paths.append(proof)
    paths.extend(p / 'capture.json' for p in roots)
    summary = dict(audio=audio, cpu_events=cpu, changed_counts={k: len(v) for k, v in changed.items()},
                   timing_gate_passed=False, rejected_reason='Worst stable gap20.858ms to23.883ms',
                   release_ready=False, original_nes_speed_verified=False, acoustic_acceptance=False)
    out.mkdir()
    cards = []
    for frame in changed['video_sha256']:
        imgs = []
        for label, root, rows in zip(('3955', '4033'), roots, (a, b)):
            name = f'{label}-{frame}.png'
            shutil.copyfile(root / rows[frame-1]['frame_image'], out / name)
            imgs.append(f'<figure><img loading="lazy" src="{name}"><figcaption>{label}</figcaption></figure>')
        cards.append(f'<h3>Frame {frame}</h3><div class="pair">'+''.join(imgs)+'</div>')
    body = '''<!doctype html><meta charset="utf-8"><title>Regular IRQ audio experiment4033</title>
<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}a{color:cyan}pre{white-space:pre-wrap}.pair{display:flex}figure{margin:8px}img{width:480px;image-rendering:pixelated}</style>
<h1>Camera pre-service removed: rejected audio regression</h1>
<p>Worst stable packet gap grows from20.858ms to23.883ms. Minimum falls from12.148ms to9.862ms. Do not promote this experiment. Sampled room game cadence remains two frames; that does not override audio failure.</p>
<p>Only early camera sound servicing is bypassed. Late-NMI-edge protection, normal line80 IRQ, pending ownership, recovery, graphics and SPC bytes are retained. No hardware deployment.</p>
<p>Frame8531 camera policy restores at line71 instead of106; sound starts at line80 instead of37. This supports the local hypothesis, not all-scene scheduling safety. Every changed picture and all full-route excluded audio intervals remain available.</p>
<p><a href="../audio-regular-irq-audio-review-4037/">Untouched native trial audio and every interval</a> · <a href="../early-oam-live-half-audio-review-3962/">Baseline audio</a> · <a href="report.json">All differences and bindings</a> · <a href="https://github.com/struktured-labs/river-city-ransom-snes/issues/6">Audio issue</a></p>
<h2>Measurements (baseline / trial)</h2><pre>'''+html.escape(json.dumps(summary, indent=2))+'</pre><h2>Every changed picture</h2>'+''.join(cards)
    (out / 'index.html').write_text(body)
    report = dict(summary=summary, changed_frames=changed, sources={str(p): sha(p) for p in paths},
                  artifacts={p.name: sha(p) for p in out.iterdir()}, scope=__doc__)
    (out / 'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(summary['changed_counts']))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    review(**vars(p.parse_args()))
