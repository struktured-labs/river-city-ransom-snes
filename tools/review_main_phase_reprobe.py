"""Publish the recovered interrupt alongside the disqualifying scrolling regression."""
import argparse
import html
import json
from pathlib import Path
import shutil

from tools import combat_campaign as combat
from tools.audit_display_cadence import observe
from tools.audit_main_display_latency import bound_report
from tools.audit_uniform_holds import summarize
from tools.benchmark_report import sha, verify_capture
from tools.frame_audit import verify_frame
from tools.review_retained_producer import authenticated_replay, compare
from tools.review_two_player_combat import stable_gaps
from tools.two_player_combat import installed_policy, validate_ports


def review(config, out):
    if out.exists():
        raise ValueError('Fresh review required')
    spec = json.loads(config.read_text())
    sources = {str(config):sha(config), str(Path(__file__)):sha(Path(__file__))}
    parent = bound_report(Path(spec['parent_publication']))
    sources.update(parent['sources'])
    sources[spec['parent_publication']] = sha(Path(spec['parent_publication']))
    out.mkdir(parents=True)
    arms = {}
    panels = []
    sounds = []
    for label, arm in spec['arms'].items():
        candidate = Path(arm['candidate'])
        proof = bound_report(Path(arm['proof']))
        if not proof['passed'] or proof['sources'].get(str(candidate/'native-cpu.sfc')) != sha(candidate/'native-cpu.sfc'):
            raise ValueError('Unqualified helper')
        sources.update(proof['sources'])
        sources[arm['proof']] = sha(Path(arm['proof']))
        normal, render = Path(arm['normal']), Path(arm['render'])
        cadence = observe(render,normal,'snes')
        if cadence['rom_sha256'] != sha(candidate/'native-cpu.sfc'):
            raise ValueError('Different rendered ROM')
        sources.update(cadence['sources'])
        _, rows = verify_capture(normal)
        park = {p:summarize(r) for p,r in cadence['phases'].items()}
        campaigns = {}
        with installed_policy():
            for policy in combat.POLICIES:
                root = Path(arm['campaigns'])
                receipt, result, game_rows, _ = combat.verify_pair(root,policy,'snes',candidate)
                records = []
                for kind in ('normal','observed'):
                    folder = root/f'{policy}-snes-{kind}'
                    for name in ('two-player.json','combat-observer.json'):
                        binding = bound_report(folder/name)
                        sources.update(binding['sources'])
                        sources[str(folder/name)] = sha(folder/name)
                    port_proof = bound_report(folder/'two-player.json')
                    record = json.loads((folder/'two-port-input.json').read_text())
                    if validate_ports(record,game_rows,'snes') != port_proof['delivery']:
                        raise ValueError('Wrong actual input ports')
                    records.append(record)
                if records[0] != records[1]:
                    raise ValueError('Observation changed controller delivery')
                campaigns[policy] = dict(frames=receipt['frames'], strict=result,
                                         stable=stable_gaps(result,game_rows,'snes'))
        episodes = []
        for n,(control_path,trial_path,event) in enumerate(zip(spec['controls'],arm['replays'],spec['events']),1):
            control, trial = Path(control_path), Path(trial_path)
            baseline, old = authenticated_replay(control)
            changed, new = authenticated_replay(trial)
            if (not baseline['passed'] or changed['trial']['resume_control'] != str(control) or
                    changed['trial']['trial_rom_sha256'] != sha(candidate/'native-cpu.sfc') or
                    baseline['initial_registers'] != changed['initial_registers'] or
                    (control/'initial.ram').read_bytes() != (trial/'initial.ram').read_bytes()):
                raise ValueError('Different or unqualified replay start')
            episodes.append(dict(event=event, comparison=compare(old,new,event)))
            for binding, folder in ((baseline,control),(changed,trial)):
                sources.update(binding['sources'])
                sources[str(folder/'report.json')] = sha(folder/'report.json')
            if label == 'phase-and-camera':
                for name,folder,window in (('before',control,old),('after',trial,new)):
                    src = folder/'audio.wav'
                    filename = f'case{n}-{name}.wav'
                    shutil.copy2(src,out/filename)
                    sources[str(src)] = sha(src)
                    sounds.append(f'<p>Exact-state case {n}: {name}</p><audio controls preload="none" src="{filename}"></audio>')
        audio = bound_report(Path(arm['audio']))
        for group in ('baseline','candidate'):
            for name,digest in audio[group]['sources'].items():
                if sha(Path(name)) != digest:
                    raise ValueError('Changed DSP source')
            sources.update(audio[group]['sources'])
        sources.update(audio['sources'])
        sources[arm['audio']] = sha(Path(arm['audio']))
        if audio['candidate']['sources'].get(str(candidate/'native-cpu.sfc')) != sha(candidate/'native-cpu.sfc'):
            raise ValueError('Different DSP cartridge')
        publication = None
        if arm.get('publication'):
            publication = bound_report(Path(arm['publication']))
            if publication['sources'].get(str(candidate/'native-cpu.sfc')) != sha(candidate/'native-cpu.sfc'):
                raise ValueError('Different latency cartridge')
            sources.update(publication['sources'])
            sources[arm['publication']] = sha(Path(arm['publication']))
        arms[label] = dict(park=park,campaigns=campaigns,episodes=episodes,
                          publication=publication,audio=audio['candidate'],cadence=cadence,
                          late_write_mutation_rejected=audio['late_write_mutation_rejected'])
        first = next(r for r in park.values() if r['short_irregular'])['short_irregular'][0]
        frames = sorted({first['start']-1,first['start'],first['end']-1,first['end']})
        cards = []
        for frame in frames:
            row = rows[frame-1]
            src = verify_frame(normal,row)
            name = f'{label}-{frame}.png'
            shutil.copy2(src,out/name)
            sources[str(src)] = sha(src)
            camera = next(r['camera'] for phase in cadence['phases'].values()
                          for r in phase['series'] if r['frame']==frame)
            cards.append(f'<figure><img src="{name}"><figcaption>Frame {frame} · rendered camera {camera}</figcaption></figure>')
        panels.append('<h3>'+html.escape(label)+'</h3><div class="grid">'+''.join(cards)+'</div>')
    for name in ('audit_display_cadence','audit_uniform_holds','review_retained_producer','review_two_player_combat',
                 'frame_audit','audit_main_display_latency','combat_campaign','two_player_combat'):
        path = Path('tools')/(name+'.py')
        sources[str(path)] = sha(path)
    summary = {label:dict(combat={p:r['stable']['frame_histogram'] for p,r in arm['campaigns'].items()},
        irregular={p:len(r['short_irregular']) for p,r in arm['park'].items()},
        recovered_events=[r['event'] for r in arm['episodes'] if all(r['comparison']['gates'].values())])
        for label,arm in arms.items()}
    report = dict(arms=arms,parent_publication=parent,sources=sources,summary=summary,
                  release_ready=False,physical_verified=False,pop_free_verified=False,
                  original_speed_parity_verified=False,
                  scope='Both earlier-main variants are rejected for scrolling jitter. One matched-state missed '
                  'interrupt is recovered; another persists. Independent combat is not matched CPU work. '
                  'Source-consistent camera tables and correct audio transport do not waive cadence or acoustics.')
    latency_rows = ''.join(f'<tr><td>{room}</td><td>{html.escape(str(parent["rooms"][room]["start_to_display"]))}</td>'
        f'<td>{html.escape(str(arms["phase-and-camera"]["publication"]["rooms"][room]["start_to_display"]))}</td></tr>'
        for room in ('0','1','2','3'))
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Earlier main: recovery and rejection</title>'
        '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:2em auto}'
        'a{color:cyan}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}figure{margin:0}'
        'img,audio{width:100%}img{image-rendering:pixelated}pre{white-space:pre-wrap}'
        'td,th{padding:8px;border:1px solid #567}</style><h1>One missed frame recovered; scrolling still disqualifies</h1>'
        '<p>Offline only. Rival unchanged. Phase64 changes eight immediates and checksum. The follow-up '
        'also changes eight camera admission immediates. Fifty phase fixtures and86 camera cases execute '
        'the production bytes; five and four broken controls are rejected.</p>'
        '<p>Same-state case4317 completes on4317 instead of4318, with unchanged pictures through4318. '
        'Case2239 still misses its interrupt. Each restore has identical128KiB WRAM, CPU registers and actual two-port input.</p>'
        '<h2>Rejected scrolling results</h2><pre>'+html.escape(json.dumps(summary,indent=2))+'</pre>'
        '<p>The parent has zero short irregular holds in both park sweeps. Both trials have many. '
        'Each full route completes8874 frames; renderer observation is neutral. No split/stale-camera '
        'failure does NOT imply smooth scrolling.</p><h2>Why a scanline cutoff is insufficient</h2>'
        '<p>Delay in frames from original main start to actual camera display; entries are delay:count. '
        'These are independent encounters, not paired-input latency measurements.</p>'
        '<table><tr><th>Room</th><th>Parent</th><th>Earlier main + camera cutoff</th></tr>'+latency_rows+'</table>'
        '<p>The follow-up still alternates one- and two-frame presentation in the park. Some camera stores '
        'finish before the first VBlank and others after it. A coherent game-tick publication policy '
        'needs testing; globally adding a frame is not a verified fix. Same-frame room-entry camera '
        'overwrites remain explicit failures in the latency evidence.</p>'+''.join(panels)+
        '<h2>Audio checks and native clips</h2><p>Each trial validates8431 received packets and1549 restarts; '
        'zero changed settings after restart, no clipping, exact raw-DAC/WAV match. This is NOT a pop-free '
        'or original-NES fidelity certificate. Clips are complete90-frame native replays without processing.</p>'+''.join(sounds)+
        '<p><a href="report.json">All source hashes, failures, loops, camera series and limitations</a></p>')
    report['artifacts'] = {p.name:sha(p) for p in out.iterdir() if p.is_file()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('config','out'):
        p.add_argument('--'+name,type=Path,required=True)
    review(**vars(p.parse_args()))
