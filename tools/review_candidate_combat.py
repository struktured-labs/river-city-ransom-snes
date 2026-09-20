"""Review two fresh SNES combat policies without implying an equal-work NES test."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import shutil
import wave

from PIL import Image

from tools.benchmark_report import sha
from tools.build_combat_outlier_review import context, excerpt_bounds, outliers
from tools.combat_campaign import POLICIES, verify_pair


def native_clip(source, target, first, last):
    """Copy exact, bounded native samples; never normalize or resample."""
    with wave.open(str(source), 'rb') as wav:
        params = wav.getparams()
        if (params.nchannels != 2 or params.sampwidth != 2 or
                not 0 <= first < last <= wav.getnframes()):
            raise ValueError('Need bounded stereo PCM16 excerpt')
        wav.setpos(first)
        pcm = wav.readframes(last-first)
    if len(pcm) != (last-first)*4:
        raise ValueError('Truncated source audio')
    with wave.open(str(target), 'wb') as wav:
        wav.setparams(params)
        wav.writeframes(pcm)
    with wave.open(str(target), 'rb') as wav:
        if (wav.getnframes() != last-first or wav.getframerate() != params.framerate or
                wav.readframes(wav.getnframes()) != pcm):
            raise ValueError('Excerpt changed native samples')
    return dict(file=target.name, source=str(source), source_sha256=sha(source),
                first_sample=first, last_sample_exclusive=last,
                rate=params.framerate, sha256=sha(target))


def build(root, candidate, out):
    if out.exists():
        raise ValueError('Fresh review required')
    # Validate both complete observer controls before producing any review.
    captures = {p: verify_pair(root, p, 'snes', candidate) for p in POLICIES}
    out.mkdir(parents=True)
    sources, results, events, cards = {}, {}, [], []
    for policy, (receipt, result, rows, normal) in captures.items():
        results[policy] = result
        for kind in ('normal', 'observed'):
            directory = root/f'{policy}-snes-{kind}'
            binding = json.loads((directory/'combat-observer.json').read_text())
            sources.update(binding['sources'])
            for filename in ('combat-observer.json', 'capture.json', 'timeline.json', 'audio.wav'):
                path = directory/filename
                sources[str(path)] = sha(path)
        cards.append(f'<h2>{policy}: {"PASS" if result["passed"] else "FAIL"}</h2>'
                     f'<p>{receipt["frames"]} frames; {len(result["iterations"])} measured loops. '
                     'Startup/other loops and censored boundaries remain in the report.</p>')
        # Publish every measured outlier, not only examples favorable to the trial.
        selected = outliers(result['iterations'], rows)
        for item in selected:
            event = context(item['loop'], rows)
            event.update(policy=policy, start_spacing=item['start_spacing'],
                         following_start_frame=item['following_start_frame'])
            first, last = event['first'], event['last']
            prefix = f'{policy}-{first}'
            cards.append(f'<h3>{prefix}: {event["frame_span"]} frames, '
                         f'{event["nmi_advances"]} NMI ticks</h3>'
                         f'<p>Room change: {event["room_change"]}. Strict failure retained.</p><div class="grid">')
            frames = sorted({max(1, first-1), first, first+1, (first+last)//2,
                             last, min(len(rows), last+1), min(len(rows), last+30)})
            event['pictures'] = []
            for frame in frames:
                source = normal/f'frames/frame-{frame:05d}.png'
                row = rows[frame-1]
                if sha(source) != row['frame_image_sha256']:
                    raise ValueError('Changed source frame')
                with Image.open(source) as image:
                    if hashlib.sha256(image.convert('RGB').tobytes()).hexdigest() != row['video_sha256']:
                        raise ValueError('Frame pixels disagree with capture')
                target = out/f'{prefix}-{frame}.png'
                shutil.copyfile(source, target)
                event['pictures'].append(dict(frame=frame, file=target.name, sha256=sha(target)))
                cards.append(f'<figure><img src="{target.name}"><figcaption>Frame {frame}</figcaption></figure>')
            begin, end, a, b = excerpt_bounds(rows, first, last)
            event['audio'] = native_clip(normal/'audio.wav', out/(prefix+'.wav'), a, b)
            event['audio'].update(first_frame=begin, last_frame=end)
            cards.append(f'</div><audio controls preload="none" src="{prefix}.wav"></audio>')
            events.append(event)
        # Keep native gameplay listening evidence even for a passing policy.
        begin, end = result['phases']['combat_take_hits']['frames']
        end = min(end, begin+299)
        a = rows[begin-1]['audio_start_sample']
        b = rows[end-1]['audio_start_sample']+rows[end-1]['audio']['samples']
        result['listening_excerpt'] = native_clip(normal/'audio.wav', out/(policy+'.wav'), a, b)
        cards.append(f'<p>First 300 requested attack/run frames, native audio:</p>'
                     f'<audio controls preload="none" src="{policy}.wav"></audio>')
    for name in (__file__, 'tools/build_combat_outlier_review.py', 'tools/combat_campaign.py',
                 'tools/audit_combat_loops.py', 'tools/audit_main_store_latency.py',
                 'tools/audit_route_loop_cadence.py', 'tools/benchmark_report.py'):
        path = Path(name)
        sources[str(path)] = sha(path)
    if any(sha(Path(p)) != digest for p, digest in sources.items()):
        raise ValueError('Sources changed while building review')
    report = dict(passed=all(r['passed'] for r in results.values()), policies=results,
                  outliers=events, sources=sources, rom_sha256=sha(candidate/'native-cpu.sfc'),
                  observer_neutral=True, release_ready=False,
                  physical_speed_verified=False, pop_free_verified=False,
                  scope='Two independent input-only SNES policies, complete same-ROM observer '
                  'timeline/PCM neutrality, unchanged strict cadence gates. Every measured '
                  'outlier retained. No equal-work NES comparison; a missing room transition '
                  'does not prove its earlier stall fixed. Native excerpts are not normalized, '
                  'resampled or time fitted. No physical audio or full-game speed verdict.')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Candidate combat regression</title>'
        '<style>body{background:#101820;color:#eef;font:16px sans-serif;max-width:1200px;margin:auto;padding:24px}'
        'a{color:#7df}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}'
        'img{width:100%;image-rendering:pixelated}figure{margin:0}audio{width:100%}</style>'
        f'<h1>Offline candidate combat: {"PASS" if report["passed"] else "FAIL"}</h1>'
        f'<p>ROM: {report["rom_sha256"]}</p><p>{html.escape(report["scope"])}</p>'
        '<p><a href="report.json">All loops, failures and source hashes</a> · '
        '<a href="manifest.json">Artifact hashes</a></p>'+''.join(cards))
    (out/'manifest.json').write_text(json.dumps(dict(sources=sources,
        artifacts={p.name: sha(p) for p in out.iterdir() if p.is_file()}, release_ready=False), indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'], outliers=len(events),
                         loops={p: len(r['iterations']) for p, r in results.items()})))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'candidate', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    build(**vars(parser.parse_args()))
