"""Full-stub ABI, measured cost, exact-state failures and rendered pacing evidence."""
import argparse
import html
import json
from pathlib import Path
import shutil

from tools import combat_campaign as combat
from tools.audit_busy_combat import measure
from tools.audit_display_cadence import observe
from tools.audit_main_display_latency import bound_report
from tools.audit_uniform_holds import summarize
from tools.benchmark_report import sha
from tools.frame_audit import verify_frame
from tools.review_retained_producer import authenticated_replay, compare
from tools.review_ring_dirty import body_intervals
from tools.two_player_combat import installed_policy, validate_ports


def review(config, out):
    if out.exists():
        raise ValueError('Fresh output required')
    spec = json.loads(config.read_text())
    sources = {}
    def bind(path):
        record = bound_report(path)
        sources.update(record.get('sources', {}))
        sources[str(path)] = sha(path)
        groups = [record.get('artifacts', {}), record.get('mutant_artifacts', {})]
        groups += [c.get('artifacts', {}) for c in record.get('cases', [])]
        for group in groups:
            for key, digest in group.items():
                p = Path(key) if key.startswith('build/') else path.parent/key
                if sha(p) != digest:
                    raise ValueError('Changed artifact: '+str(p))
        return record
    control = Path(spec['control'])
    before, old = authenticated_replay(control)
    bind(control/'report.json')
    if not before['passed']:
        raise ValueError('Failed same-ROM control')
    timing = bind(Path(spec['timing'])/'report.json')
    if not timing['observer_neutral']:
        raise ValueError('Non-neutral timing observer')
    arms, summary, cards, clips = {}, [], [], []
    out.mkdir(parents=True)
    def media(name, folder, rows):
        for row in rows:
            if row['frame'] not in (2237,2238,2239,2240):
                continue
            verify_frame(folder,row)
            source = folder/row['frame_image']
            target = f'{name}-{row["frame"]}.png'
            shutil.copy2(source,out/target)
            sources[str(source)] = sha(source)
            cards.append(f'<figure><img src="{target}"><figcaption>{html.escape(name)} '
                         f'· {row["frame"]}</figcaption></figure>')
        source = folder/'audio.wav'
        shutil.copy2(source,out/(name+'.wav'))
        sources[str(source)] = sha(source)
        clips.append(f'<p>{html.escape(name)}</p><audio controls src="{name}.wav"></audio>')
    media('parent',control,old)
    for name, raw in spec['arms'].items():
        paths = {k:Path(v) for k,v in raw.items()}
        candidate, replay = paths['candidate'],paths['replay']
        proof = bind(paths['oracle']/'report.json')
        changed, new = authenticated_replay(replay)
        bind(replay/'report.json')
        if (not proof['passed'] or len(proof['cases']) != 432 or
                not all(m['rejected'] for m in proof['mutants']) or
                proof['sources'].get(str(candidate/'native-cpu.sfc')) != sha(candidate/'native-cpu.sfc') or
                not changed['cross_rom_restore_verified'] or
                changed['trial']['resume_control'] != str(control) or
                changed['trial']['trial_rom_sha256'] != sha(candidate/'native-cpu.sfc') or
                changed['trial']['parent_rom_sha256'] != before['sources'][spec['parent']+'/native-cpu.sfc'] or
                (control/'initial.ram').read_bytes() != (replay/'initial.ram').read_bytes()):
            raise ValueError('Wrong oracle/ROM/initial-state/control')
        with installed_policy():
            receipt, result, rows, _ = combat.verify_pair(paths['campaigns'],'running-jumps','snes',candidate)
        logs = []
        for kind in ('normal','observed'):
            folder = paths['campaigns']/f'running-jumps-snes-{kind}'
            bind(folder/'combat-observer.json')
            port = bind(folder/'two-player.json')
            log = json.loads((folder/'two-port-input.json').read_text())
            if validate_ports(log,rows,'snes') != port['delivery']:
                raise ValueError('Wrong input delivery')
            logs.append(log)
        if logs[0] != logs[1]:
            raise ValueError('Observer changed actual two-port inputs')
        busy = measure(result,rows)
        display = observe(paths['renderer'],paths['route'],'snes')
        sources.update(display['sources'])
        held = {p:summarize(r) for p,r in display['phases'].items()}
        renderer = bind(paths['renderer_audit']/'report.json')
        causal = compare(old,new,2239)
        arms[name] = dict(same_state=causal,event_recovered=all(causal['gates'].values()),
            strict_combat=result, including_busy=busy, combat_frames=receipt['frames'],
            display=display, uniform_holds=held, renderer_audit=renderer,
            full_stub_cases=len(proof['cases']), mutants=proof['mutants'])
        summary.append(dict(arm=name,known_stall_recovered=arms[name]['event_recovered'],
            strict_combat_passed=result['passed'], combat_intervals=busy['frame_histogram'],
            camera={p:dict(histogram=r['histogram'],short_irregular=len(r['short_irregular']))
                    for p,r in held.items()}))
        media(name,replay,new)
    bodies, bindings = body_intervals(Path(spec['arms']['fusion-tile']['candidate']),Path(spec['instructions']))
    sources.update(bindings)
    own = [Path(__file__),config,Path('tools/review_retained_producer.py'),Path('tools/review_ring_dirty.py'),
           Path('tools/audit_busy_combat.py'),Path('tools/audit_display_cadence.py'),
           Path('tools/audit_uniform_holds.py'),Path('tools/frame_audit.py'),Path('tests/test_ppu_fusion.py')]
    sources.update({str(p):sha(p) for p in own})
    for p,digest in sources.items():
        if sha(Path(p)) != digest:
            raise ValueError('Changed source: '+p)
    report = dict(arms=arms,timing=timing['cases'],original_interrupts=bodies,sources=sources,
        release_ready=False,physical_verified=False,pop_free_verified=False,scope=__doc__+
        ' Neither saved-state stall is recovered. Fresh-boot passing combat cannot replace '
        'that failure. No fresh menu/DSP/main-to-display/physical qualification.')
    savings = [r['saved_clocks'] for r in timing['cases']]
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>PPU stub fusion</title>'
        '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1150px;margin:2em auto}'
        'a{color:cyan}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}figure{margin:0}'
        'img,audio{width:100%}img{image-rendering:pixelated}pre{white-space:pre-wrap}</style>'
        '<h1>Faster PPU writes — known stall still open</h1><p>Offline candidates; Rival unchanged. '
        'Each candidate passes432 whole-stub cases and rejects four deliberate faults. '
        'Actual ordinary/coroutine returns and interrupt-enable behavior execute in the fixture.</p>'
        f'<p>All18 stubs measured in two cases each: {min(savings)}–{max(savings)} master clocks saved. '
        'Not a whole-game speedup claim.</p><h2>Combat and actual rendered pacing</h2><pre>'+
        html.escape(json.dumps(summary,indent=2))+'</pre><p>Neither candidate is promoted. '
        'All pauses and failures remain in the detailed report.</p>'
        '<h2>Same-state frames2237–2240</h2><p>Rows: parent, fusion, fusion-tile. '
        'The affected update still completes on2240, with matching pictures through that frame.</p>'
        '<div class="grid">'+''.join(cards)+'</div><h2>Native replay audio</h2>'
        '<p>Exact, unnormalized output from the replay; no pop-free or fidelity claim.</p>'+''.join(clips)+
        '<p>Fixture scope: selected safe stack positions, not all possible stack-wrap behavior. '
        'Original coroutine resume destinations lead to ABI recorders; their subsequent task bodies '
        'are covered by the separate integration runs, not these isolated fixtures.</p>'
        '<p><a href="report.json">Measurements, failures, source and artifact hashes</a></p>')
    report['artifacts'] = {p.name:sha(p) for p in out.iterdir() if p.is_file()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(summary=summary,sources=len(sources),artifacts=len(report['artifacts']))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('config','out'):
        p.add_argument('--'+name,type=Path,required=True)
    review(**vars(p.parse_args()))
