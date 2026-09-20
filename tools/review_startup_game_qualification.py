"""Combine current-game startup timing, renderer, and two-player stress evidence."""
import argparse
import json
from pathlib import Path
import shutil

from tools import combat_campaign as combat
from tools.audit_busy_combat import measure
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.frame_audit import verify_frame
from tools.review_candidate_combat import native_clip
from tools.review_two_player_combat import observed_play
from tools.two_player_combat import installed_policy, validate_ports


def review(candidate, audio, renderer, campaigns, out):
    if out.exists():
        raise ValueError('Fresh qualification review required')
    sound = bound_report(audio/'report.json')
    picture = bound_report(renderer/'report.json')
    digest = sha(candidate/'native-cpu.sfc')
    if sound['rom_sha256'] != digest:
        raise ValueError('Different audio cartridge')
    # Renderer report sources contain both observer/control capture receipts.
    receipts = [Path(p) for p in picture['sources'] if p.endswith('/capture.json')]
    if len(receipts) != 2 or any(json.loads(p.read_text())['rom_sha256'] != digest for p in receipts):
        raise ValueError('Different renderer cartridge')
    renderer_receipts = [json.loads(p.read_text()) for p in receipts]
    if renderer_receipts[0]['core_sha256'] != renderer_receipts[1]['core_sha256']:
        raise ValueError('Renderer needs actual same-core observer control')
    sources = dict(sound['sources'], **picture['sources'])
    results, panels, clips = {}, [], []
    out.mkdir()
    with installed_policy():
        for policy in combat.POLICIES:
            receipt, strict, rows, normal = combat.verify_pair(campaigns, policy, 'snes', candidate)
            busy = measure(strict, rows)
            play = observed_play(rows)
            inputs = []
            for kind in ('normal', 'observed'):
                root = campaigns/f'{policy}-snes-{kind}'
                port = bound_report(root/'two-player.json')
                records = json.loads((root/'two-port-input.json').read_text())
                if validate_ports(records, rows, 'snes') != port['delivery']:
                    raise ValueError('Input delivery changed')
                inputs.append(records)
                for name in ('two-player.json', 'combat-observer.json'):
                    p = root/name; sources.update(bound_report(p)['sources']); sources[str(p)] = sha(p)
                for name in ('capture.json', 'timeline.json', 'audio.wav'):
                    p = root/name; sources[str(p)] = sha(p)
            if inputs[0] != inputs[1]:
                raise ValueError('Observer changed controller input')
            results[policy] = dict(frames=receipt['frames'], strict=strict, including_busy=busy,
                                   actual_two_player_movement=play)
            for phase in ('combat_take_hits', 'combat_counterattack'):
                selected = [r for r in rows if r['phase'] == phase]
                row = selected[-1]
                source = verify_frame(normal, row); sources[str(source)] = sha(source)
                filename = f'{policy}-{phase}.png'; shutil.copyfile(source, out/filename)
                panels.append(f'<figure><img src="{filename}"><figcaption>{policy} · {phase} · frame {row["frame"]}</figcaption></figure>')
            first = [r for r in rows if r['phase'] == 'combat_take_hits'][0]['frame']
            last = first+299
            clips.append(native_clip(normal/'audio.wav', out/(policy+'.wav'),
                rows[first-1]['audio_start_sample'], rows[last-1]['audio_start_sample']+rows[last-1]['audio']['samples']))
    for p in (Path(__file__), Path('tools/audit_busy_combat.py'), Path('tools/combat_campaign.py'),
              Path('tools/two_player_combat.py'), Path('tools/review_two_player_combat.py'),
              Path('tools/review_candidate_combat.py'), Path('tools/frame_audit.py'),
              audio/'report.json', renderer/'report.json', candidate/'manifest.json', candidate/'native-cpu.sfc'):
        sources[str(p)] = sha(p)
    gates = dict(restart_timing=sound['restart_timing_passed'], four_room_cadence=sound['route_cadence']['passed'],
                 renderer=picture['passed'], two_player_strict=all(r['strict']['passed'] for r in results.values()),
                 two_player_including_busy=all(r['including_busy']['passed'] for r in results.values()))
    report = dict(rom_sha256=digest, qualified_checks=gates, tested_checks_passed=all(gates.values()),
        audio_review=str(audio), renderer_review=str(renderer), combat=results, clips=clips,
        sources=sources, release_ready=False, hardware_tested=False,
        remaining=['DMA qualification for this exact ROM', 'all four menu regression suites',
                   'broader full-game and original-NES audio/speed coverage', 'physical Bluemage audio/video'],
        scope='Scoped current-ROM checks, not closure of cross-ROM differences or promotion. '
              'Busy flag stays in combat denominator; every exclusion/outlier remains in source reports.')
    html = '<!doctype html><meta charset="utf-8"><title>Startup-pitch game qualification</title>'
    html += '<style>body{background:#111a26;color:#eef;font:17px system-ui;max-width:1150px;margin:30px auto}'
    html += 'a{color:#8df}.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}figure{margin:0}img{width:100%;image-rendering:pixelated}audio{width:100%}</style>'
    html += '<h1>Offline game build: restart-pitch staging</h1>'
    html += f'<p>ROM <code>{digest}</code>. No upload-length or game-code change; no hardware deployment.</p>'
    html += '<p>Verified gates: '+', '.join(f'{k}: {v}' for k, v in gates.items())+'</p>'
    html += f'<p><a href="../{audio.name}/">All1,607 restart checks, parent/trial audio, changed frames and cadence</a> · '
    html += f'<a href="../{renderer.name}/">Complete renderer coverage and retained exclusions</a></p>'
    html += '<p>Cross-ROM picture/RAM/callback differences remain documented. Menus, DMA, broader '
    html += 'NES fidelity and physical capture remain open; this is not a pop-free or release claim.</p>'
    for name, r in results.items():
        html += f'<h2>{name}</h2><p>{r["frames"]:,} frames; {r["including_busy"]["intervals"]:,} '
        html += f'busy-inclusive intervals; histogram {r["including_busy"]["frame_histogram"]}. '
        html += 'Both players’ delivered inputs and actual movement are checked.</p>'
        html += f'<audio controls preload="none" src="{name}.wav"></audio>'
    html += '<div class="grid">'+''.join(panels)+'</div><p><a href="report.json">Complete bound evidence</a></p>'
    (out/'index.html').write_text(html)
    report['artifacts'] = {p.name: sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(gates=gates, combat={k: r['including_busy']['frame_histogram'] for k, r in results.items()})))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'audio', 'renderer', 'campaigns', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    review(**vars(p.parse_args()))
