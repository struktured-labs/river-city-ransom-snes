"""Publish bounded combat progress, queue identities, scrolling checks and failed picture gates."""
import argparse
import csv
import html
import json
from pathlib import Path
import shutil

from tools import combat_campaign as combat
from tools.audit_busy_combat import measure
from tools.audit_display_cadence import observe
from tools.audit_main_display_latency import bound_report
from tools.audit_restored_clock import decode,reconstruct,expired_events
from tools.audit_retained_service import identity_gates
from tools.audit_uniform_holds import summarize
from tools.benchmark_report import sha,verify_capture
from tools.build_retained_producer_guard import symbols
from tools.frame_audit import verify_frame
from tools.review_retained_producer import authenticated_replay,compare,counters
from tools.two_player_combat import installed_policy,validate_ports


def review(candidate,oracle,campaigns,instructions,route,renderer,renderer_audit,trace,
           control,trial,earlier_control,earlier_trial,out):
    if out.exists():raise ValueError('Fresh evidence required')
    sources={};rom=candidate/'native-cpu.sfc';rom_hash=sha(rom)
    def bind(path):
        r=bound_report(path);sources.update(r['sources']);sources[str(path)]=sha(path);return r
    def same_candidate(r):
        if r['sources'].get(str(rom))!=rom_hash:raise ValueError('Different candidate proof')
    fixture=bind(oracle/'report.json');same_candidate(fixture)
    if not fixture['passed']:raise ValueError('Fixture failed')
    for case in fixture['cases']+fixture['negative_controls']:
        for p,d in case['artifacts'].items():
            if sha(Path(p))!=d:raise ValueError('Changed executed fixture')
            sources[p]=d
    with installed_policy():
        receipt,strict,rows,_=combat.verify_pair(campaigns,'running-jumps','snes',candidate)
    logs=[]
    for kind in ('normal','observed'):
        root=campaigns/f'running-jumps-snes-{kind}'
        bind(root/'combat-observer.json');p=bind(root/'two-player.json')
        log=json.loads((root/'two-port-input.json').read_text())
        if validate_ports(log,rows,'snes')!=p['delivery']:raise ValueError('Changed input delivery')
        logs.append(log)
    if logs[0]!=logs[1]:raise ValueError('Observer changed inputs')
    busy=measure(strict,rows)
    ip=bind(instructions/'instruction-control.json');pp=bind(instructions/'two-player-instructions.json')
    same_candidate(ip)
    if not ip['observer_neutral'] or not pp['observer_neutral']:raise ValueError('Nonneutral instruction core')
    with installed_policy(),combat.installed('running-jumps'):
        ir,ir_rows=verify_capture(instructions)
    if ir_rows!=rows or ir['audio_sha256']!=receipt['audio_sha256']:
        raise ValueError('Instruction and sparse-core outputs differ')
    instruction_csv=instructions.with_suffix('.csv')
    if ip['sources'].get(str(instruction_csv))!=sha(instruction_csv):raise ValueError('Unbound instructions')
    image=rom.read_bytes();priority=symbols(candidate/'retained-entry.lbl')['owned_queue_priority']
    priority_entries=[]
    with instruction_csv.open() as stream:
        for row in csv.reader(stream):
            pc=int(row[4],16)
            if image[pc&0x3fffff]!=int(row[5],16):raise ValueError('Incorrect executed opcode')
            if pc&65535==priority:priority_entries.append(dict(frame=int(row[0]),line=int(row[1]),clock=int(row[3]),pc=pc))
    if not priority_entries:raise ValueError('New priority helper never executed')
    display=observe(renderer,route,'snes');sources.update(display['sources'])
    if display['rom_sha256']!=rom_hash:raise ValueError('Different renderer candidate')
    rendered=bind(renderer_audit/'report.json')
    holds={k:summarize(v) for k,v in display['phases'].items()}
    proof=bind(trace/'report.json');same_candidate(proof)
    if not proof['passed'] or not proof['observed'] or not proof['queue_accounting']:
        raise ValueError('Nonneutral or unbalanced replay trace')
    with (trace/'instructions.csv').open() as stream:clock_rows=[decode(r) for r in csv.reader(stream)]
    clock=reconstruct(clock_rows,proof['first'],proof['last'],image)
    q=json.loads((trace/'queue.json').read_text());initial=q['initial']
    final=next(r for r in q['frames'] if r['frame']==proof['last'])
    boot=symbols(candidate/'native_boot.lbl');ins=[r for r in clock_rows if r['kind']=='I']
    bodies=[r for r in ins if 0xc1<=r['pc']>>16<=0xc8 and r['pc']&65535==0xff4f]
    packets=[r for r in ins if r['pc']>>16 in (0,0xc0) and r['pc']&65535==boot['spc_frame']]
    identity,wanted=identity_gates(initial['native_id'],final['native_id'],
        [r['nmi_count'] for r in bodies],[r['nmi_count'] for r in packets])
    expired=expired_events(clock_rows,boot['nmi']);identity['no_unserved_flag_expiry']=not expired
    sound=dict(gates=identity,wanted=wanted,bodies=bodies,packets=packets,expired=expired,clock=clock,
        intervals=[b['clock']-a['clock'] for a,b in zip(packets,packets[1:])],
        scope='CPU sender entries and real original body identities in seven traced frames; not DSP or pop-free qualification.')
    out.mkdir(parents=True);panels=[];clips=[];comparisons={}
    for name,old_path,new_path,start,end in (('newer',control,trial,2249,2252),
                                            ('earlier',earlier_control,earlier_trial,2237,2241)):
        before,old=authenticated_replay(old_path);after,new=authenticated_replay(new_path)
        if (not before['passed'] or not after['cross_rom_restore_verified'] or
            after['trial']['trial_rom_sha256']!=rom_hash or after['trial']['resume_control']!=str(old_path) or
            (old_path/'initial.ram').read_bytes()!=(new_path/'initial.ram').read_bytes()):
            raise ValueError('Unqualified exact-state replay')
        if name=='earlier':comparisons[name]=compare(old,new,2239)
        else:
            if [r['frame'] for r in old]!=[r['frame'] for r in new]:raise ValueError('Different frame windows')
            comparisons[name]=dict(series=[dict(before=counters(a),after=counters(b),
                same_picture=a['video_sha256']==b['video_sha256']) for a,b in zip(old,new)])
        cards=[]
        for label,root,timeline in (('parent',old_path,old),('candidate',new_path,new)):
            bind(root/'report.json')
            for row in timeline:
                if not start<=row['frame']<=end:continue
                source=verify_frame(root,row);target=f'{name}-{label}-{row["frame"]}.png'
                shutil.copy2(source,out/target);sources[str(source)]=sha(source)
                cards.append(f'<figure><img src="{target}"><figcaption>{label} · {row["frame"]}</figcaption></figure>')
            source=root/'audio.wav';target=f'{name}-{label}.wav'
            shutil.copy2(source,out/target);sources[str(source)]=sha(source)
            if (out/target).read_bytes()!=source.read_bytes():raise ValueError('Changed native audio')
            clips.append(dict(file=target,source=str(source)))
        panels.append(f'<h2>{name.title()} saved-state replay</h2><div class="grid" style="grid-template-columns:repeat({end-start+1},1fr)">'+''.join(cards)+'</div>')
    summary=dict(combat_frames=receipt['frames'],strict_passed=strict['passed'],
        including_busy_passed=busy['passed'],interval_histogram=busy['frame_histogram'],
        fixture_cases=len(fixture['cases']),negative_controls=len(fixture['negative_controls']),
        renderer_passed=rendered['passed'],holds={k:dict(histogram=v['histogram'],
            short_irregular=len(v['short_irregular'])) for k,v in holds.items()},
        sound_identity_gates=identity,sound_sender_intervals=sound['intervals'],
        earlier_gates=comparisons['earlier']['gates'])
    for p in (Path(__file__),Path('tools/audit_retained_service.py'),Path('tools/audit_restored_clock.py'),
              Path('tools/review_retained_producer.py'),Path('tools/audit_busy_combat.py'),
              Path('tools/audit_display_cadence.py'),Path('tools/audit_uniform_holds.py'),
              Path('tools/frame_audit.py'),candidate/'native_boot.lbl',candidate/'retained-entry.lbl'):
        sources[str(p)]=sha(p)
    report=dict(summary=summary,combat=dict(strict=strict,including_busy=busy),renderer=rendered,
        display=display,holds=holds,sound=sound,comparisons=comparisons,priority_entries=priority_entries,
        clips=clips,sources=sources,release_ready=False,physical_verified=False,pop_free_verified=False,
        scope=__doc__+' No new menu or full-route DSP qualification. No original-NES whole-game speed claim.')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Owned queue priority</title>'
        '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1200px;margin:2em auto}'
        'a{color:cyan}.grid{display:grid;gap:8px}figure{margin:0}img{width:100%;image-rendering:pixelated}'
        'pre{white-space:pre-wrap}audio{width:80%}</style><h1>Combat hitch cleared in this test; still offline</h1>'
        '<p>Candidate 2990 gives an already-queued interrupt priority over owned graphics preparation. '
        'Deferred graphics work keeps its ownership. Rivalmage and Bluemage have not been touched.</p>'
        '<p>The full 4,929-frame running-jump capture passes its strict timing test, including pause/resume. '
        'The busy-inclusive subset has 1,753 two-frame intervals and no irregular intervals. '
        'This is one deterministic scenario, not an original-NES or full-game speed certificate.</p>'
        '<p>The earlier picture comparison still FAILS. The candidate is not cleared for deployment. '
        'New menu tests and full-route DSP checks remain outstanding; sound is not certified pop-free.</p>'
        '<pre>'+html.escape(json.dumps(summary,indent=2))+'</pre>'+''.join(panels)+
        '<h2>Native replay audio</h2><p>Exact, unnormalized 90-frame clips; no filtering or gain changes. '
        'Ordered CPU packets do not prove smooth audio.</p>'+''.join(
        f'<p>{c["file"]}</p><audio controls preload="none" src="{c["file"]}"></audio>' for c in clips)+
        '<p><a href="report.json">Bound proofs, failures, exact intervals and qualification limits</a></p>')
    for p,d in sources.items():
        if sha(Path(p))!=d:raise ValueError('Changed bound source: '+p)
    report['artifacts']={p.name:sha(p) for p in out.iterdir() if p.is_file()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(summary))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('candidate','oracle','campaigns','instructions','route','renderer','renderer-audit','trace',
              'control','trial','earlier-control','earlier-trial','out'):
        p.add_argument('--'+k,type=Path,required=True)
    review(**vars(p.parse_args()))
