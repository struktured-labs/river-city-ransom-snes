"""Compare failed scheduling alternatives, actual sprite DMA recovery, combat, renderer and DSP evidence."""
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
from tools.benchmark_report import sha
from tools.build_retained_producer_guard import symbols
from tools.frame_audit import verify_frame
from tools.review_retained_producer import authenticated_replay,compare,counters
from tools.two_player_combat import installed_policy,validate_ports


def review(config,out):
    if out.exists():raise ValueError('Fresh output required')
    spec=json.loads(config.read_text());sources={str(config):sha(config)}
    def bind(path):
        r=bound_report(path);sources.update(r['sources']);sources[str(path)]=sha(path);return r
    baseline,old=authenticated_replay(Path(spec['control']));bind(Path(spec['control'])/'report.json')
    if not baseline['passed']:raise ValueError('Same-ROM control failed')
    out.mkdir(parents=True);arms={};cards=[];clips=[];table=[]
    for name,values in spec['arms'].items():
        candidate,replay=Path(values['candidate']),Path(values['replay'])
        rp,new=authenticated_replay(replay);bind(replay/'report.json');rom=candidate/'native-cpu.sfc'
        if (not rp['cross_rom_restore_verified'] or rp['trial']['trial_rom_sha256']!=sha(rom) or
            rp['trial']['resume_control']!=spec['control'] or
            (replay/'initial.ram').read_bytes()!=(Path(spec['control'])/'initial.ram').read_bytes()):
            raise ValueError('Different cartridge/state')
        comparison=compare(old,new,2239)
        with installed_policy():
            receipt,result,rows,_=combat.verify_pair(Path(values['combat']),'running-jumps','snes',candidate)
        logs=[]
        for kind in ('normal','observed'):
            root=Path(values['combat'])/f'running-jumps-snes-{kind}'
            bind(root/'combat-observer.json');ports=bind(root/'two-player.json')
            log=json.loads((root/'two-port-input.json').read_text())
            if validate_ports(log,rows,'snes')!=ports['delivery']:raise ValueError('Wrong port delivery')
            logs.append(log)
        if logs[0]!=logs[1]:raise ValueError('Observer changed inputs')
        busy=measure(result,rows);arm=dict(comparison=comparison,strict=result,including_busy=busy)
        if values.get('trace'):
            root=Path(values['trace']);proof=bind(root/'report.json');image=rom.read_bytes()
            if not proof['passed'] or not proof['observed'] or proof['sources'].get(str(rom))!=sha(rom):
                raise ValueError('Wrong or nonneutral trace')
            with (root/'instructions.csv').open() as stream:trace=[decode(r) for r in csv.reader(stream)]
            clock=reconstruct(trace,proof['first'],proof['last'],image)
            ins=[r for r in trace if r['kind']=='I'];boot=symbols(candidate/'native_boot.lbl')
            # Authenticate the actual OAM source, 544-byte size and DMA channel
            # setup in the executed cartridge; pair STA420B with its next CPU
            # instruction to measure the transfer, not just function entry.
            marker=bytes.fromhex('a200508e0243a97e8d0443a220028e0543a9018d0b42')
            if image[:65536].count(marker)!=1:raise ValueError('Different full OAM DMA')
            dma=image.index(marker)+len(marker)-3
            transfers=[]
            for i,r in enumerate(ins[:-1]):
                if r['pc']>>16 in (0,0xc0) and r['pc']&65535==dma:
                    nxt=ins[i+1]
                    if nxt['pc']!=r['pc']+3 or r['a']&255!=1 or r['x']!=544:
                        raise ValueError('Changed OAM transfer execution')
                    transfers.append(dict(start=r,end=nxt,clocks=nxt['clock']-r['clock']))
            q=json.loads((root/'queue.json').read_text());last=next(x for x in q['frames'] if x['frame']==proof['last'])
            bodies=[r for r in ins if 0xc1<=r['pc']>>16<=0xc8 and r['pc']&65535==0xff4f]
            packets=[r for r in ins if r['pc']>>16 in (0,0xc0) and r['pc']&65535==boot['spc_frame']]
            gates,wanted=identity_gates(q['initial']['native_id'],last['native_id'],
                [r['nmi_count'] for r in bodies],[r['nmi_count'] for r in packets])
            expired=expired_events(trace,boot['nmi']);gates['no_unserved_flag_expiry']=not expired
            arm['trace']=dict(clock=clock,transfers=transfers,bodies=bodies,packets=packets,
                wanted=wanted,gates=gates,expired=expired,final_entries=[r for r in ins
                if r['pc']>>16 in (0,0xc0) and r['pc']&65535==boot['final_room']])
            sources[str(candidate/'native_boot.lbl')]=sha(candidate/'native_boot.lbl')
        arms[name]=arm
        table.append(f'<tr><td>{html.escape(name)}</td><td>{comparison["gates"]["same_picture_through_following_frame"]}</td>'
            f'<td>{result["passed"]}</td><td>{html.escape(str(busy["frame_histogram"]))}</td></tr>')
        rows_html=[]
        for row in new:
            if not 2237<=row['frame']<=2241:continue
            source=verify_frame(replay,row);target=f'{name}-{row["frame"]}.png';shutil.copy2(source,out/target)
            sources[str(source)]=sha(source);rows_html.append(f'<figure><img src="{target}"><figcaption>{row["frame"]}</figcaption></figure>')
        cards.append('<h3>'+html.escape(name)+'</h3><div class="grid">'+''.join(rows_html)+'</div>')
        if name in ('priority','slack'):
            source=replay/'audio.wav';target=name+'.wav';shutil.copy2(source,out/target)
            sources[str(source)]=sha(source);clips.append(dict(file=target,source=str(source)))
    parent_cards=[]
    for row in old:
        if not 2237<=row['frame']<=2241:continue
        source=verify_frame(Path(spec['control']),row);target=f'parent-{row["frame"]}.png';shutil.copy2(source,out/target)
        sources[str(source)]=sha(source);parent_cards.append(f'<figure><img src="{target}"><figcaption>{row["frame"]}</figcaption></figure>')
    candidate=Path(spec['arms']['slack']['candidate']);rom=candidate/'native-cpu.sfc'
    fixture=bind(Path(spec['oracle'])/'report.json')
    if not fixture['passed'] or fixture['sources'].get(str(rom))!=sha(rom):raise ValueError('Wrong batch fixture')
    for case in fixture['cases']+fixture['negative_controls']:
        for p,d in case['artifacts'].items():
            if sha(Path(p))!=d:raise ValueError('Changed fixture artifact')
            sources[p]=d
    display=observe(Path(spec['renderer']),Path(spec['route']),'snes');sources.update(display['sources'])
    if display['rom_sha256']!=sha(rom):raise ValueError('Wrong rendered cartridge')
    rendered=bind(Path(spec['renderer_audit'])/'report.json')
    holds={k:summarize(v) for k,v in display['phases'].items()}
    dsp=bind(Path(spec['dsp'])/'report.json')
    for label in ('candidate','baseline'):
        for p,d in dsp[label]['sources'].items():
            if sha(Path(p))!=d:raise ValueError('Changed DSP source')
            sources[p]=d
    if dsp['candidate']['sources'].get(str(rom))!=sha(rom):raise ValueError('Wrong DSP cartridge')
    before,old_newer=authenticated_replay(Path(spec['newer_control']));after,new_newer=authenticated_replay(Path(spec['newer']))
    for p in (Path(spec['newer_control'])/'report.json',Path(spec['newer'])/'report.json'):bind(p)
    if (not before['passed'] or not after['cross_rom_restore_verified'] or
        after['trial']['trial_rom_sha256']!=sha(rom) or after['trial']['resume_control']!=spec['newer_control']):
        raise ValueError('Wrong newer replay')
    newer=[dict(before=counters(a),after=counters(b),same_picture=a['video_sha256']==b['video_sha256'])
           for a,b in zip(old_newer,new_newer)]
    for p in (Path(__file__),Path('tools/audit_restored_clock.py'),Path('tools/audit_retained_service.py'),
        Path('tools/review_retained_producer.py'),Path('tools/frame_audit.py'),Path('tools/audit_busy_combat.py'),
        Path('tools/audit_display_cadence.py'),Path('tools/audit_uniform_holds.py')):sources[str(p)]=sha(p)
    summary=dict(earlier_gates=arms['slack']['comparison']['gates'],combat=arms['slack']['including_busy']['frame_histogram'],
        renderer_passed=rendered['passed'],holds={k:dict(histogram=v['histogram'],short_irregular=len(v['short_irregular'])) for k,v in holds.items()},
        actual_batch_cases=len(fixture['cases']),latest_fixture_finish=max(c['finish_line'] for c in fixture['cases']),
        dsp={k:dsp['candidate'][k] for k in ('passed','packets','restarts','late_restarts','pcm_samples','pcm_peak','clipped_samples')})
    report=dict(summary=summary,arms=arms,fixture=fixture,display=display,holds=holds,renderer=rendered,dsp=dsp,newer=newer,
        clips=clips,sources=sources,release_ready=False,physical_verified=False,pop_free_verified=False,
        scope=__doc__+' No new menus or full-game/original-NES parity. One-line slack is experimentally qualified only in the recorded cases.')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Sprite deadline recovery</title>'
        '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1200px;margin:2em auto}'
        'a{color:cyan}.grid{display:grid;grid-template-columns:repeat(5,1fr);gap:8px}figure{margin:0}'
        'img{width:100%;image-rendering:pixelated}td,th{padding:8px;border:1px solid #567}pre{white-space:pre-wrap}</style>'
        '<h1>Sprite deadline recovered without losing this combat timing test</h1>'
        '<p>Candidate 3032 remains offline; neither MiSTer was touched. Rivalmage is occupied, Bluemage permitted.</p>'
        '<p>The old publisher reached its final-batch check at line 249, cycle 1338, then latched line 250 '
        'and refused the sprite transfer. Allowing the batch through line 250 restores the missing picture. '
        'The boundary fixture reads all 544 physical OAM bytes and completes the full batch by line 257.</p>'
        '<p>Two scan-stopping alternatives also fixed the picture, but introduced combat hitches. Their failures '
        'are retained below. The one-line-slack trial passes the fresh combat test; this is not whole-game speed certification.</p>'
        '<table><tr><th>Trial</th><th>Earlier picture gate</th><th>Strict combat</th><th>Busy-inclusive intervals</th></tr>'+''.join(table)+'</table>'
        '<details><summary>Renderer, boundary and audio metrics</summary><pre>'+html.escape(json.dumps(summary,indent=2))+'</pre></details>'
        '<h2>Exact saved-state pictures</h2><h3>Original parent</h3><div class="grid">'+''.join(parent_cards)+'</div>'+''.join(cards)+
        '<h2>Native 90-frame audio clips</h2><p>No normalization or filtering. DSP ordering is tested separately; '
        'pop-free sound is not established. New menu regression coverage and physical qualification remain.</p>'+''.join(
        f'<p>{c["file"]}</p><audio controls preload="none" src="{c["file"]}"></audio>' for c in clips)+
        '<p><a href="report.json">All bound sources, failed alternatives, DMA traces and qualification limits</a></p>')
    for p,d in sources.items():
        if sha(Path(p))!=d:raise ValueError('Changed source '+p)
    report['artifacts']={p.name:sha(p) for p in out.iterdir() if p.is_file()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(summary))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('config','out'):p.add_argument('--'+k,type=Path,required=True)
    review(**vars(p.parse_args()))
