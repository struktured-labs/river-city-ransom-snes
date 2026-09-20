"""Expose every campaign timing outlier with native PCM and exact frame context."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import shutil
import wave

from PIL import Image

from tools.benchmark_report import sha
from tools.combat_campaign import review, verify_pair


def outliers(loops, rows):
    selected = []
    for i, loop in enumerate(loops):
        first = loop['start']['frame']
        following = loops[i+1]['start']['frame'] if i+1 < len(loops) else None
        same_phase = following is not None and rows[first-1]['phase'] == rows[following-1]['phase']
        spacing = following-first if same_phase else None
        if (loop['nmi_advances'] != 2 or loop['finish']['frame']-first != 2
                or spacing not in (None, 2)):
            selected.append(dict(loop=loop, following_start_frame=following if same_phase else None,
                                 start_spacing=spacing))
    return selected


def context(loop, rows):
    first, last = loop['start']['frame'], loop['finish']['frame']
    if not 1 <= first <= last <= len(rows):
        raise ValueError('Outlier outside complete timeline')
    sample = rows[first-1:last]
    states = []
    for row in sample:
        ram = bytes.fromhex(row['game_ram_hex'])
        if len(ram) != 2048:
            raise ValueError('Need full original game RAM')
        states.append(dict(frame=row['frame'], room=ram[0x42], task=ram[0x100],
            pause_flags=ram[0x3f], game_mode=ram[0x3e],
            transition=row.get('native', {}).get('transition_state'),
            audio_ac_rms=row['audio']['ac_rms']))
    return dict(first=first, last=last, nmi_advances=loop['nmi_advances'],
        frame_span=last-first, states=states,
        room_change=len({s['room'] for s in states}) > 1,
        native_transition_observed=any(s['transition'] not in (None, 0) for s in states),
        # This annotation is intentionally not used to waive a failed gate.
        strict_gate_waived=False)


def excerpt_bounds(rows, first, last):
    begin, end = max(1, first-30), min(len(rows), last+30)
    return (begin, end, rows[begin-1]['audio_start_sample'],
            rows[end-1]['audio_start_sample']+rows[end-1]['audio']['samples'])


def build(root, candidate, out):
    review(root, candidate, out)
    report = json.loads((out/'report.json').read_text())
    page = (out/'index.html').read_text()
    page += '<h1>Every non-two-tick loop: original evidence</h1><p>Room transitions are annotated, not removed from the failed strict gate. Audio clips use native sample boundaries with no gain adjustment, resampling or time fitting.</p>'
    events = []
    for policy, systems in report['runs'].items():
        for system, result in systems.items():
            _, _, rows, normal = verify_pair(root, policy, system, candidate)
            with wave.open(str(normal/'audio.wav'), 'rb') as wav:
                params = wav.getparams()
                pcm = wav.readframes(wav.getnframes())
            for selected in outliers(result['iterations'], rows):
                loop = selected['loop']
                event = context(loop, rows)
                event.update(following_start_frame=selected['following_start_frame'],
                             start_spacing=selected['start_spacing'])
                first, last = event['first'], event['last']
                name = f'{policy}-{system}-{first}'
                page += f'<h2>{name}: {event["nmi_advances"]} ticks / {event["frame_span"]} emulator frame span / {event["start_spacing"]} start spacing</h2>'
                page += f'<p>Room change: {event["room_change"]}; native transition observed: {event["native_transition_observed"]}. Strict failure retained.</p><div class="grid">'
                frames = sorted({max(1, first-1), first, first+1, (first+last)//2,
                                 last, min(len(rows), last+1), min(len(rows), last+30)})
                pictures = []
                for frame in frames:
                    row = rows[frame-1]
                    source = normal/f'frames/frame-{frame:05d}.png'
                    if sha(source) != row['frame_image_sha256']:
                        raise ValueError('Frame image hash mismatch')
                    with Image.open(source) as im:
                        if hashlib.sha256(im.convert('RGB').tobytes()).hexdigest() != row['video_sha256']:
                            raise ValueError('Image pixels disagree with captured video')
                    dest = f'{name}-{frame}.png'
                    shutil.copyfile(source, out/dest)
                    pictures.append(dict(frame=frame, file=dest, sha256=sha(source)))
                    page += f'<figure><img src="{dest}"><figcaption>Frame {frame}</figcaption></figure>'
                begin, end, a, b = excerpt_bounds(rows, first, last)
                block = params.nchannels*params.sampwidth
                if not 0 <= a < b <= len(pcm)//block:
                    raise ValueError('Clip outside native audio')
                dest = name+'.wav'
                with wave.open(str(out/dest), 'wb') as wav:
                    wav.setparams(params)
                    wav.writeframes(pcm[a*block:b*block])
                with wave.open(str(out/dest), 'rb') as wav:
                    if wav.readframes(wav.getnframes()) != pcm[a*block:b*block]:
                        raise ValueError('Listening excerpt changed')
                event.update(policy=policy, system=system, pictures=pictures,
                    audio=dict(file=dest, source=str(normal/'audio.wav'), source_sha256=sha(normal/'audio.wav'),
                               first_sample=a, last_sample_exclusive=b, first_frame=begin, last_frame=end,
                               rate=params.framerate, sha256=sha(out/dest)))
                events.append(event)
                page += f'</div><audio controls preload="none" src="{dest}"></audio>'
                page += '<p>State at each frame: '+html.escape(str(event['states']))+'</p>'
    (out/'outliers.json').write_text(json.dumps(events, indent=2)+'\n')
    page += '<p><a href="outliers.json">Full frame states and native clip boundaries</a></p>'
    (out/'index.html').write_text(page)
    manifest = json.loads((out/'manifest.json').read_text())
    manifest['sources'][str(Path(__file__))] = sha(Path(__file__))
    manifest['artifacts'] = {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'manifest.json'}
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(dict(out=str(out), outliers=len(events), strict_passed=report['passed'])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'candidate', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    build(**vars(parser.parse_args()))
