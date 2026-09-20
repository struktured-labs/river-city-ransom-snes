"""Retain exact-state failures beside faster PPU calls and independent game tests."""
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
from tools.review_retained_producer import authenticated_replay,compare
from tools.review_ring_dirty import body_intervals
from tools.two_player_combat import installed_policy,validate_ports


def review(config,out):
    if out.exists():
        raise ValueError('Fresh output required')
    spec = json.loads(config.read_text())
    sources = {}
    def bind(path):
        record = bound_report(path)
        sources.update(record.get('sources',{}))
        sources[str(path)] = sha(path)
        for key,digest in record.get('artifacts',{}).items():
            artifact = Path(key) if key.startswith('build/') else path.parent/key
            if sha(artifact)!=digest:
                raise ValueError('Changed artifact: '+str(artifact))
        for case in record.get('cases',[]):
            for key,digest in case.get('artifacts',{}).items():
                if sha(Path(key))!=digest:
                    raise ValueError('Changed fixture artifact')
        return record
    control = Path(spec['control'])
    baseline,old = authenticated_replay(control)
    if not baseline['passed']:
        raise ValueError('Same-ROM control failed')
    bind(control/'report.json')
    timing = bind(Path(spec['timing'])/'report.json')
    if not timing['observer_neutral']:
        raise ValueError('Non-neutral timing probe')
    for name in ('oracle','edges'):
        if not bind(Path(spec[name])/'report.json')['passed']:
            raise ValueError('Helper oracle failed')
    out.mkdir(parents=True)
    arms,summary,cards,audio = {},[],[],[]
    for name,raw in spec['arms'].items():
        paths = {k:Path(v) for k,v in raw.items()}
        candidate,replay = paths['candidate'],paths['replay']
        proof = bind(paths['proof']/'report.json')
        changed,new = authenticated_replay(replay)
        bind(replay/'report.json')
        if (not proof['passed'] or changed['trial']['resume_control']!=str(control) or
                changed['trial']['trial_rom_sha256']!=sha(candidate/'native-cpu.sfc') or
                (control/'initial.ram').read_bytes()!=(replay/'initial.ram').read_bytes()):
            raise ValueError('Wrong proof/state/cartridge')
        with installed_policy():
            receipt,result,rows,_ = combat.verify_pair(paths['campaigns'],'running-jumps','snes',candidate)
        logs = []
        for kind in ('normal','observed'):
            folder = paths['campaigns']/f'running-jumps-snes-{kind}'
            bind(folder/'combat-observer.json')
            port = bind(folder/'two-player.json')
            log = json.loads((folder/'two-port-input.json').read_text())
            if validate_ports(log,rows,'snes')!=port['delivery']:
                raise ValueError('Wrong P0/P1 delivery')
            logs.append(log)
        if logs[0]!=logs[1]:
            raise ValueError('Observer changed controller stream')
        busy = measure(result,rows)
        display = observe(paths['renderer'],paths['route'],'snes')
        sources.update(display['sources'])
        held = {p:summarize(r) for p,r in display['phases'].items()}
        renderer = bind(paths['renderer_audit']/'report.json')
        causal = compare(old,new,2239)
        arms[name] = dict(same_state=causal,event_recovered=all(causal['gates'].values()),
            strict_combat=result,including_busy=busy,combat_frames=receipt['frames'],
            display=display,uniform_holds=held,renderer_audit=renderer,
            helper_cases=proof['helper_cases'],independent_cases=proof['independent_cases'])
        summary.append(dict(arm=name,known_state_recovered=arms[name]['event_recovered'],
            strict_combat_passed=result['passed'],including_busy=busy['frame_histogram'],
            park={p:dict(histogram=r['histogram'],short_irregular=len(r['short_irregular'])) for p,r in held.items()}))
        for row in new:
            if row['frame'] not in (2237,2238,2239,2240):
                continue
            verify_frame(replay,row)
            source = replay/row['frame_image']
            target = f'{name}-{row["frame"]}.png'
            shutil.copy2(source,out/target)
            sources[str(source)] = sha(source)
            cards.append(f'<figure><img src="{target}"><figcaption>{html.escape(name)} · '
                         f'{row["frame"]}</figcaption></figure>')
        shutil.copy2(replay/'audio.wav',out/(name+'.wav'))
        sources[str(replay/'audio.wav')] = sha(replay/'audio.wav')
        audio.append(f'<p>{html.escape(name)}</p><audio controls src="{name}.wav"></audio>')
    earlier = {}
    for name,folder in spec['earlier_replays'].items():
        report,rows = authenticated_replay(Path(folder))
        bind(Path(folder)/'report.json')
        if report['trial']['resume_control']!=str(control):
            raise ValueError('Different earlier replay control')
        earlier[name] = compare(old,rows,2239)
    for row in old:
        if row['frame'] not in (2237,2238,2239,2240):
            continue
        verify_frame(control,row)
        source = control/row['frame_image']
        target = f'parent-{row["frame"]}.png'
        shutil.copy2(source,out/target)
        sources[str(source)] = sha(source)
        cards.append(f'<figure><img src="{target}"><figcaption>parent · {row["frame"]}</figcaption></figure>')
    shutil.copy2(control/'audio.wav',out/'parent.wav')
    sources[str(control/'audio.wav')] = sha(control/'audio.wav')
    bodies,bindings = body_intervals(Path(spec['arms']['write-and-tile']['candidate']),Path(spec['instructions']))
    sources.update(bindings)
    own = [Path(__file__),config,Path('tools/review_retained_producer.py'),Path('tools/review_ring_dirty.py'),
           Path('tools/audit_busy_combat.py'),Path('tools/audit_display_cadence.py'),Path('tools/audit_uniform_holds.py'),
           Path('tools/frame_audit.py'),Path('tests/test_ppu_register.py')]
    sources.update({str(p):sha(p) for p in own})
    for path,digest in sources.items():
        if sha(Path(path))!=digest:
            raise ValueError('Changed source: '+path)
    report = dict(arms=arms,earlier_replays=earlier,timing=timing['cases'],original_interrupts=bodies,
        sources=sources,release_ready=False,physical_verified=False,pop_free_verified=False,
        scope=__doc__+' Neither exact-state completion is recovered. A passing new encounter does not '
        'supersede that failure. No fresh full menu, DSP, main-to-display latency or physical qualification.')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>PPU write overhead</title>'
        '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1150px;margin:2em auto}'
        'a{color:cyan}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}figure{margin:0}'
        'img,audio{width:100%}img{image-rendering:pixelated}pre{white-space:pre-wrap}</style>'
        '<h1>Faster register writes; not a completed interrupt fix</h1><p>Offline. Rival unchanged. '
        '270 helper comparisons,246 independent checks and four executed mutants. '
        '18 static PPU stubs are retargeted across eight banks; generic I/O stays unchanged.</p>'
        '<p>Measured dispatcher calls save204–280 master clocks each (26–34%). '
        'No percentage whole-game speedup is inferred.</p><h2>Keep both positive and negative results</h2><pre>'+
        html.escape(json.dumps(summary,indent=2))+'</pre><p>Fresh-boot write-and-tile combat passes, but '
        'the old saved-state stall remains and westbound scrolling has two uneven holds. '
        'Write-only scrolling is steady; one combat stall remains. Neither is promoted.</p>'
        '<h2>Exact-state frames2237–2240</h2><p>Rows: write-only, write-and-tile, parent. '
        'Same starting WRAM/registers and both input streams. Each still finishes the affected update '
        'on2240. All later differences remain in the report.</p><div class="grid">'+''.join(cards)+'</div>'
        '<h2>Native replay audio</h2><p>Parent</p><audio controls src="parent.wav"></audio>'+''.join(audio)+
        '<p>Exact unnormalized emulator output; no acoustic pass is claimed.</p>'
        '<h2>Fixture limitation retained</h2><p>Exploratory original-dispatcher tests fail at '
        'SP0–2 and corrupt DP at SP7–8, where native word/long-call stack operations cross page1. '
        'These are not counted as passing tests. The qualified matrix explicitly scopes its stack positions.</p>'
        '<p><a href="report.json">All failures, clock spans, counters, hashes and limitations</a></p>')
    report['artifacts'] = {p.name:sha(p) for p in out.iterdir() if p.is_file()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(summary=summary,sources=len(sources),artifacts=len(report['artifacts']))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('config','out'):
        p.add_argument('--'+name,type=Path,required=True)
    review(**vars(p.parse_args()))
