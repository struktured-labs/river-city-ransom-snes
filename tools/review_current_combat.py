"""Current two-player cadence, retaining busy frames and all failed intervals."""
import argparse
import html
import json
from pathlib import Path
import shutil
from tools import combat_campaign as combat
from tools.audit_busy_combat import measure
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.review_two_player_combat import observed_play
from tools.two_player_combat import installed_policy, validate_ports


def review(root, candidate, out):
    if out.exists():
        raise ValueError('Fresh report required')
    sources = {}
    results = {}
    copies = []
    with installed_policy():
        for policy in combat.POLICIES:
            receipt, result, rows, normal = combat.verify_pair(root, policy, 'snes', candidate)
            ports = []
            for kind in ('normal', 'observed'):
                folder = root / f'{policy}-snes-{kind}'
                for name in ('two-player.json', 'combat-observer.json'):
                    proof = bound_report(folder / name)
                    sources.update(proof['sources'])
                    sources[str(folder/name)] = sha(folder/name)
                record = json.loads((folder/'two-port-input.json').read_text())
                proof = bound_report(folder/'two-player.json')
                if validate_ports(record, rows, 'snes') != proof['delivery']:
                    raise ValueError('Changed port delivery')
                ports.append(record)
            if ports[0] != ports[1]:
                raise ValueError('Observer changed controller input')
            busy = measure(result, rows)
            results[policy] = dict(frames=receipt['frames'], strict=result,
                including_busy=busy, players=observed_play(rows),
                faults=[r['frame'] for r in rows if r['fault']])
            # All off-cadence windows, plus representative attack outcomes.
            frames = {r['frame'] for r in rows if r['phase'] in
                      ('combat_take_hits', 'combat_counterattack') and
                      (r['frame'] == len(rows) or rows[r['frame']]['phase'] != r['phase'])}
            for span in busy['off_cadence']:
                frames.update(range(span['first'], span['last']+1))
            for frame in sorted(frames):
                row = rows[frame-1]
                src = normal/row['frame_image']
                if sha(src) != row['frame_image_sha256']:
                    raise ValueError('Changed picture')
                copies.append((src, f'{policy}-{frame}.png'))
            copies.append((normal/'audio.wav', f'{policy}.wav'))
    for name in (__file__, 'tools/audit_busy_combat.py', 'tools/combat_campaign.py',
                 'tools/audit_combat_loops.py', 'tools/audit_main_store_latency.py',
                 'tools/two_player_combat.py', 'tools/review_two_player_combat.py'):
        sources[name] = sha(Path(name))
    out.mkdir(parents=True)
    for src, name in copies:
        sources[str(src)] = sha(src)
        shutil.copyfile(src, out/name)
    summary = {p:dict(frames=r['frames'], histogram=r['including_busy']['frame_histogram'],
                     off_cadence=len(r['including_busy']['off_cadence']), faults=r['faults'])
               for p, r in results.items()}
    body = ('<!doctype html><meta charset="utf-8"><title>Current combat cadence</title>'
        '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:2em auto}'
        'a{color:cyan}img{width:384px;image-rendering:pixelated}pre{white-space:pre-wrap}</style>'
        '<h1>Two-player combat — current candidate 3800</h1>'
        '<p>Same-core observer/control equality across full video/input/state/native PCM. '
        'Busy frames remain in cadence measurements. All excluded and censored loops are retained. '
        'Not matched NES workload, whole-game speed, or pop-free audio approval.</p><pre>'
        + html.escape(json.dumps(summary, indent=2)) + '</pre>')
    for p in results:
        body += f'<h2>{p}</h2><audio controls preload="none" src="{p}.wav"></audio>'
        for _, name in copies:
            if name.startswith(p) and name.endswith('.png'):
                body += f'<figure><img src="{name}"><figcaption>{name}</figcaption></figure>'
    body += '<p><a href="report.json">All intervals and bindings</a> · <a href="../progress-3728/">Progress</a></p>'
    (out/'index.html').write_text(body)
    if any(sha(Path(p)) != h for p, h in sources.items()):
        raise ValueError('Changed source during review')
    report = dict(results=results, sources=sources, summary=summary,
        artifacts={p.name:sha(p) for p in out.iterdir()},
        rom_sha256=sha(candidate/'native-cpu.sfc'), observer_neutral=True,
        matched_nes_speed_verified=False, release_ready=False)
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'candidate', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    review(**vars(parser.parse_args()))
