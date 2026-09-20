"""Compare the park-entry audio handoff, retaining full-route primary differences."""
import argparse
import csv
import html
import json
from pathlib import Path
import shutil
import wave
from tools.audit_main_display_latency import bound_report
from tools.audit_sound_service_phases import MS_PER_CLOCK
from tools.benchmark_report import sha, verify_capture


def review(before, after, out):
    if out.exists():
        raise ValueError('Fresh output required')
    sources = {str(Path(__file__)): sha(Path(__file__))}
    runs, timelines = {}, {}
    for name, folder in (('before', before), ('after', after)):
        proof = bound_report(folder / 'service-instructions.json')
        if not proof['observer_neutral'] or (proof['first'], proof['last']) != (7114, 7116):
            raise ValueError('Wrong or non-neutral observation')
        receipt, rows = verify_capture(folder)
        sources.update(proof['sources'])
        sources[str(folder / 'service-instructions.json')] = sha(folder / 'service-instructions.json')
        timelines[name] = rows
        events = []
        for r in csv.reader(Path(proof['trace']).open()):
            if len(r) != 10:
                raise ValueError('Wrong instruction trace geometry')
            events.append(dict(frame=int(r[0]), line=int(r[1]), cycle=int(r[2]),
                clock=int(r[3]), pc=int(r[4], 16), opcode=int(r[5], 16),
                a=int(r[6]), x=int(r[7]), y=int(r[8]), stack=int(r[9])))
        def site(pc):
            return [r for r in events if 0xc1 <= r['pc'] >> 16 <= 0xc8 and r['pc'] & 65535 == pc]
        entries, returns = site(0xfa54), site(0xfa64)
        if ([r['frame'] for r in entries] != [7114, 7115, 7116]
                or [r['frame'] for r in returns] != [7114, 7115, 7116]
                or any(a['stack'] != b['stack'] or a['clock'] >= b['clock'] for a, b in zip(entries, returns))):
            raise ValueError('Missing, nested, or unmatched driver calls')
        runs[name] = dict(rom_sha256=receipt['rom_sha256'], entries=entries, returns=returns,
            return_gaps_ms=[(b['clock']-a['clock'])*MS_PER_CLOCK for a,b in zip(returns,returns[1:])],
            camera=site(0x325c), eligibility=site(0x7bb4),
            sampled_control_frames=len(rows), replay_seconds=proof['replay_seconds'])
    a, b = timelines['before'], timelines['after']
    if len(a) != len(b):
        raise ValueError('Different full-route lengths; cannot pair frames')
    differences = {key: [x['frame'] for x,y in zip(a,b) if x[key] != y[key]]
                   for key in ('probe_052b','input_requested','input_delivered','video_sha256')}
    differences['logical_camera'] = [x['frame'] for x,y in zip(a,b)
        if x['native']['logical_camera_x'] != y['native']['logical_camera_x']]
    improved = runs['after']['return_gaps_ms'][0] < runs['before']['return_gaps_ms'][0]
    out.mkdir()
    for name, folder in (('before', before), ('after', after)):
        # Same unaligned native sample interval:117–121s, including park_entry.
        with wave.open(str(folder / 'audio.wav')) as source:
            if (source.getframerate(),source.getnchannels(),source.getsampwidth()) != (32040,2,2):
                raise ValueError('Unexpected native PCM format')
            source.setpos(117*32040)
            payload = source.readframes(4*32040)
            if len(payload) != 4*32040*4:
                raise ValueError('Truncated native audio')
        with wave.open(str(out / (name+'.wav')), 'wb') as target:
            target.setnchannels(2); target.setsampwidth(2); target.setframerate(32040)
            target.writeframes(payload)
        sources[str(folder / 'audio.wav')] = sha(folder / 'audio.wav')
        for frame in sorted(set((7114,7115,7116)) | set(differences['video_sha256'])):
            path = folder / timelines[name][frame-1]['frame_image']
            shutil.copyfile(path, out / f'{name}-{frame}.png')
            sources[str(path)] = sha(path)
    summary = dict(runs=runs, difference_counts={k:len(v) for k,v in differences.items()},
                   targeted_return_gap_improved=improved)
    body = ('<!doctype html><meta charset="utf-8"><title>Park-entry audio handoff</title>'
        '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}'
        'a{color:cyan}pre{white-space:pre-wrap}.pair{display:flex;gap:12px}img{width:48%;image-rendering:pixelated}</style>'
        '<h1>Park-entry audio: exact handoff comparison</h1><p>Full-route same-core observer neutrality. '
        'Three traced CPU frames;117–121s native PCM clips, no gain changes or alignment. '
        'All route differences retained in JSON. No pop-free, full-speed, or release verdict.</p>')
    for name in runs:
        body += f'<h2>{name}</h2><audio controls preload="none" src="{name}.wav"></audio>'
    for frame in (7114,7115,7116):
        body += f'<h2>Frame {frame}</h2><div class="pair">'
        for name in runs:
            body += f'<img src="{name}-{frame}.png" alt="{name} frame{frame}">'
        body += '</div>'
    body += '<h2>Every changed full-route picture</h2>'
    for frame in differences['video_sha256']:
        body += f'<h3>Frame {frame}</h3><div class="pair">'
        for name in runs:
            body += f'<img loading="lazy" src="{name}-{frame}.png" alt="{name} changed frame{frame}">'
        body += '</div>'
    body += '<pre>'+html.escape(json.dumps(summary,indent=2))+'</pre><a href="report.json">All differences and source hashes</a>'
    (out / 'index.html').write_text(body)
    for path in (Path('tools/audit_main_display_latency.py'),Path('tools/audit_sound_service_phases.py'),Path('tools/benchmark_report.py')):
        sources[str(path)] = sha(path)
    if any(sha(Path(p)) != h for p,h in sources.items()):
        raise ValueError('Changed evidence')
    report = dict(summary=summary,differences=differences,sources=sources,
        artifacts={p.name:sha(p) for p in out.iterdir()},release_ready=False,
        pop_free_verified=False,scope=__doc__)
    (out / 'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('before','after','out'):
        p.add_argument('--'+k,type=Path,required=True)
    review(**vars(p.parse_args()))
