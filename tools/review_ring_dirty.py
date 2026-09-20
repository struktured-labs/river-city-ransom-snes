"""Copy cost, unchanged combat failure, actual scrolling, and exact replay evidence."""
import argparse
import csv
import html
import json
from pathlib import Path
import shutil

from tools import combat_campaign as combat
from tools.audit_busy_combat import measure as busy_measure
from tools.audit_display_cadence import observe
from tools.audit_main_display_latency import bound_report
from tools.audit_uniform_holds import summarize
from tools.benchmark_report import sha, verify_capture
from tools.build_retained_producer_guard import symbols
from tools.frame_audit import verify_frame
from tools.review_retained_producer import authenticated_replay, compare
from tools.two_player_combat import installed_policy, validate_ports


def body_intervals(candidate, capture):
    proof = bound_report(capture/'instruction-control.json')
    ports = bound_report(capture/'two-player-instructions.json')
    rom = candidate/'native-cpu.sfc'
    trace = capture.with_suffix('.csv')
    if (not proof['observer_neutral'] or not ports['observer_neutral'] or
            proof['sources'].get(str(rom)) != sha(rom) or
            proof['sources'].get(str(trace)) != sha(trace)):
        raise ValueError('Unqualified instruction window')
    image = rom.read_bytes()
    entry = 0xff4f
    end = symbols(candidate/'native_runtime.lbl')['nmi_rti_return']
    first_bytes = image[65536+entry:65536+entry+3]
    if first_bytes[0] != 0x2c:
        raise ValueError('Wrong original NMI entry')
    started = None
    result = []
    for row in csv.reader(trace.open()):
        pc = int(row[4],16)
        if pc>>16 not in range(0xc1,0xc9) or pc&65535 not in (entry,end):
            continue
        at = (pc&0x3fffff)
        if int(row[5],16) != image[at]:
            raise ValueError('Trace opcode disagrees with ROM')
        record = dict(frame=int(row[0]),line=int(row[1]),cycle=int(row[2]),clock=int(row[3]),pc=pc)
        if pc&65535 == entry:
            if started is not None or image[at:at+3] != first_bytes:
                raise ValueError('Nested or different original NMI')
            started = record
        elif started is not None:
            if record['clock'] <= started['clock']:
                raise ValueError('Nonmonotonic instruction clock')
            result.append(dict(start=started,end=record,clocks=record['clock']-started['clock'],
                               crosses_frame_end=record['frame']!=started['frame']))
            started = None
    if not result:
        raise ValueError('No complete original interrupt')
    return result,{**proof['sources'],**ports['sources'],
                   str(capture/'instruction-control.json'):sha(capture/'instruction-control.json'),
                   str(capture/'two-player-instructions.json'):sha(capture/'two-player-instructions.json')}


def review(config,out):
    if out.exists():
        raise ValueError('Fresh output required')
    settings = json.loads(config.read_text())
    control = Path(settings['control'])
    baseline,old = authenticated_replay(control)
    if not baseline['passed']:
        raise ValueError('Same-ROM restore must pass')
    sources = dict(baseline['sources'])
    sources[str(control/'report.json')] = sha(control/'report.json')
    out.mkdir(parents=True)
    arms = {}
    cards = []
    summaries = []
    audio = []
    for name,values in settings['arms'].items():
        paths = {k:Path(v) for k,v in values.items()}
        candidate,oracle,timing,replay = [paths[k] for k in ('candidate','oracle','timing','replay')]
        proof = bound_report(oracle/'report.json')
        cost = bound_report(timing/'report.json')
        changed,new = authenticated_replay(replay)
        if (not proof['passed'] or not cost['observer_neutral'] or
                proof['sources'].get(str(candidate/'native-cpu.sfc')) != sha(candidate/'native-cpu.sfc') or
                changed['trial']['resume_control'] != str(control) or
                changed['trial']['trial_rom_sha256'] != sha(candidate/'native-cpu.sfc') or
                (control/'initial.ram').read_bytes() != (replay/'initial.ram').read_bytes()):
            raise ValueError('Different cartridge or initial state')
        for record in proof['cases']:
            for path,digest in record['artifacts'].items():
                if sha(Path(path)) != digest:
                    raise ValueError('Changed executed fixture: '+path)
        for report in (proof,cost,changed):
            sources.update(report['sources'])
        for path in (oracle/'report.json',timing/'report.json',replay/'report.json'):
            sources[str(path)] = sha(path)
        with installed_policy():
            receipt,result,rows,_ = combat.verify_pair(paths['campaigns'],'running-jumps','snes',candidate)
        input_logs = []
        for kind in ('normal','observed'):
            folder = paths['campaigns']/f'running-jumps-snes-{kind}'
            for filename in ('combat-observer.json','two-player.json'):
                binding = bound_report(folder/filename)
                sources.update(binding['sources'])
                sources[str(folder/filename)] = sha(folder/filename)
            log = json.loads((folder/'two-port-input.json').read_text())
            if validate_ports(log,rows,'snes') != binding['delivery']:
                raise ValueError('Wrong input delivery')
            input_logs.append(log)
        if input_logs[0] != input_logs[1]:
            raise ValueError('Observation changed controllers')
        measured = busy_measure(result,rows)
        route,route_rows = verify_capture(paths['route'])
        if not route['capture_complete'] or route['rom_sha256'] != sha(candidate/'native-cpu.sfc'):
            raise ValueError('Incomplete or wrong route')
        for filename in ('capture.json','timeline.json','audio.wav'):
            p = paths['route']/filename
            sources[str(p)] = sha(p)
        bodies,bindings = body_intervals(candidate,paths['instructions'])
        sources.update(bindings)
        causal = compare(old,new,2239)
        arms[name] = dict(timing=cost['cases'],oracle_cases=len(proof['cases']),
            independent_cases=sum(r['independent_oracle'] for r in proof['cases']),
            same_state=causal,event_recovered=all(causal['gates'].values()),
            strict_combat=result,including_busy=measured,combat_frames=receipt['frames'],
            route_frames=route['frames'],route_complete=True,original_interrupts=bodies)
        summaries.append(dict(arm=name,copy_clocks=[r['arms']['after']['clocks'] for r in cost['cases']],
            combat_histogram=measured['frame_histogram'],event_recovered=arms[name]['event_recovered'],
            route_frames=route['frames']))
        for row in new:
            if row['frame'] not in (2237,2238,2239,2240):
                continue
            verify_frame(replay,row)
            source = replay/row['frame_image']
            target = f'{name}-{row["frame"]}.png'
            shutil.copy2(source,out/target)
            sources[str(source)] = sha(source)
            cards.append(f'<figure><img src="{target}"><figcaption>{html.escape(name)} · '
                         f'frame {row["frame"]}</figcaption></figure>')
        target = name+'.wav'
        shutil.copy2(replay/'audio.wav',out/target)
        sources[str(replay/'audio.wav')] = sha(replay/'audio.wav')
        audio.append(f'<p>{html.escape(name)}</p><audio controls src="{target}"></audio>')
    for row in old:
        if row['frame'] not in (2237,2238,2239,2240):
            continue
        verify_frame(control,row)
        source = control/row['frame_image']
        target = f'parent-{row["frame"]}.png'
        shutil.copy2(source,out/target)
        sources[str(source)] = sha(source)
        cards.append(f'<figure><img src="{target}"><figcaption>parent · frame {row["frame"]}</figcaption></figure>')
    shutil.copy2(control/'audio.wav',out/'parent.wav')
    sources[str(control/'audio.wav')] = sha(control/'audio.wav')
    renderer,normal = Path(settings['renderer']),Path(settings['renderer_normal'])
    display = observe(renderer,normal,'snes')
    holds = {p:summarize(v) for p,v in display['phases'].items()}
    sources.update(display['sources'])
    for name in ('renderer_audit','mutants'):
        path = Path(settings[name])/'report.json'
        binding = bound_report(path)
        sources.update(binding['sources']);sources[str(path)] = sha(path)
        if name == 'mutants':
            if not binding['passed'] or not all(r['rejected'] for r in binding['mutants']):
                raise ValueError('Negative control survived')
            for artifact,digest in binding['artifacts'].items():
                if sha(path.parent/artifact) != digest:
                    raise ValueError('Changed mutant artifact')
    report = dict(arms=arms,actual_display=display,uniform_holds=holds,
        release_ready=False,physical_verified=False,pop_free_verified=False,
        sources=sources,scope=__doc__+' Fresh-boot encounters are not matched workloads. '
        'The saved-state comparison is causal and does not recover the failed completion. '
        'Full traversal completion is not an audio/menu/latency qualification. Rival unchanged.')
    own = [Path(__file__),config,Path('tools/audit_busy_combat.py'),Path('tools/audit_display_cadence.py'),
           Path('tools/audit_uniform_holds.py'),Path('tools/review_retained_producer.py'),
           Path('tools/frame_audit.py'),Path('tests/test_ring_dirty.py')]
    report['sources'].update({str(p):sha(p) for p in own})
    for name,digest in report['sources'].items():
        if sha(Path(name)) != digest:
            raise ValueError('Source changed during review: '+name)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Copy optimization and interrupt stall</title>'
        '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1150px;margin:2em auto}'
        'a{color:cyan}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}figure{margin:0}'
        'img,audio{width:100%}img{image-rendering:pixelated}pre{white-space:pre-wrap}</style>'
        '<h1>Faster copies; the remaining missed frame is not fixed</h1><p>Offline only. '
        'Stride32-only copies take35–36% fewer measured clocks. Each candidate passes217 full-WRAM '
        'comparisons and180 independent checks. The tile-only helper also rejects five additional '
        'executed corruption controls. Neither candidate recovers the saved-state completion.</p>'
        '<h2>Whole-game checks retain the failure</h2><pre>'+html.escape(json.dumps(summaries,indent=2))+'</pre>'
        '<p>The combined linear cache moves an earlier missed interrupt in the saved-state replay; '
        'a new test explicitly rejects treating that as recovery. Both fresh-boot combat campaigns '
        'retain one three-frame interval, including the original NMI-busy frame.</p>'
        '<h2>Actual tile-only park scrolling</h2><pre>'+html.escape(json.dumps({p:dict(histogram=r['histogram'],
            short_irregular=len(r['short_irregular'])) for p,r in holds.items()},indent=2))+'</pre>'
        '<p>Renderer observation matches the entire normal timeline and PCM. Holds and long stops '
        'are retained; this is not original-speed parity or physical scrolling proof.</p>'
        '<h2>Saved-state frames2237–2240</h2><p>Rows: combined cache, tile-only cache, parent. '
        'Exact frame positions and decoded pixels verified; no alignment.</p><div class="grid">'+''.join(cards)+'</div>'
        '<h2>Native saved-state audio</h2><p>Parent</p><audio controls src="parent.wav"></audio>'+''.join(audio)+
        '<p>Exact unnormalized emulator output. No pop-free or waveform-fidelity verdict.</p>'
        '<p><a href="report.json">Every interval, failure, source hash and artifact</a></p>')
    report['artifacts'] = {p.name:sha(p) for p in out.iterdir() if p.is_file()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(arms=summaries,holds={p:r['histogram'] for p,r in holds.items()},
                         source_bindings=len(sources),artifacts=len(report['artifacts']))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('config','out'):
        p.add_argument('--'+name,type=Path,required=True)
    review(**vars(p.parse_args()))
