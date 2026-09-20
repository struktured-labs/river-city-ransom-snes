"""Publish copy-cost improvement without concealing unchanged stalls or route death."""
import argparse
import html
import json
from pathlib import Path
import shutil

from tools import combat_campaign as combat
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha,verify_capture
from tools.review_retained_producer import authenticated_replay,compare
from tools.review_two_player_combat import stable_gaps
from tools.two_player_combat import installed_policy,validate_ports


def review(candidate,oracle,timing,campaigns,route,control1,trial1,control2,trial2,out):
    if out.exists():raise ValueError('Fresh output required')
    proof=bound_report(oracle/'report.json');cost=bound_report(timing/'report.json')
    if not proof['passed'] or not cost['observer_neutral']:raise ValueError('Unqualified fixture')
    receipt,route_rows=verify_capture(route)
    if receipt['rom_sha256']!=sha(candidate/'native-cpu.sfc'):raise ValueError('Wrong route cartridge')
    sources={**proof['sources'],**cost['sources']};results=[];cards=[];audio=[]
    out.mkdir(parents=True)
    for index,(control,trial,event) in enumerate(((control1,trial1,2239),(control2,trial2,4317)),1):
        baseline,old=authenticated_replay(control);changed,new=authenticated_replay(trial)
        if (not baseline['passed'] or changed['trial']['resume_control']!=str(control) or
                changed['trial']['trial_rom_sha256']!=sha(candidate/'native-cpu.sfc') or
                (control/'initial.ram').read_bytes()!=(trial/'initial.ram').read_bytes()):
            raise ValueError('Unqualified saved-state comparison')
        result=compare(old,new,event);results.append(result)
        sources.update(baseline['sources']);sources.update(changed['sources'])
        for label,folder,rows in (('before',control,old),('after',trial,new)):
            sources[str(folder/'report.json')]=sha(folder/'report.json')
            name=f'case{index}-{label}.wav';shutil.copy2(folder/'audio.wav',out/name)
            sources[str(folder/'audio.wav')]=sha(folder/'audio.wav')
            audio.append(f'<p>Case {index} · {label}</p><audio controls src="{name}"></audio>')
        for a,b in zip(old,new):
            if a['frame'] not in (event-1,event,event+1):continue
            for label,folder,row in (('before',control,a),('after',trial,b)):
                src=folder/row['frame_image'];name=f'case{index}-{label}-{row["frame"]}.png'
                if sha(src)!=row['frame_image_sha256']:raise ValueError('Changed screenshot')
                shutil.copy2(src,out/name);sources[str(src)]=sha(src)
                cards.append(f'<figure><img src="{name}"><figcaption>{label} · frame {row["frame"]}</figcaption></figure>')
    details={}
    with installed_policy():
        for policy in combat.POLICIES:
            _,result,rows,_=combat.verify_pair(campaigns,policy,'snes',candidate)
            records=[]
            for kind in ('normal','observed'):
                folder=campaigns/f'{policy}-snes-{kind}'
                for name in ('combat-observer.json','two-player.json'):
                    binding=bound_report(folder/name);sources.update(binding['sources'])
                    sources[str(folder/name)]=sha(folder/name)
                log=json.loads((folder/'two-port-input.json').read_text())
                if validate_ports(log,rows,'snes')!=binding['delivery']:raise ValueError('Changed ports')
                records.append(log)
            if records[0]!=records[1]:raise ValueError('Observation changed inputs')
            details[policy]=dict(strict=result,stable=stable_gaps(result,rows,'snes'))
    failures=[]
    for frame in (9300,9360,9387,10428):
        row=route_rows[frame-1];src=route/row['frame_image'];name=f'route-{frame}.png'
        if sha(src)!=row['frame_image_sha256']:raise ValueError('Changed failed-route picture')
        shutil.copy2(src,out/name);sources[str(src)]=sha(src)
        failures.append(f'<figure><img src="{name}"><figcaption>Failed route · {frame}</figcaption></figure>')
    paths=[Path(__file__),Path('tools/review_retained_producer.py'),Path('tools/review_two_player_combat.py'),
        Path('tools/audit_route_loop_cadence.py'),Path('tools/audit_main_display_latency.py'),
        oracle/'report.json',timing/'report.json',route/'capture.json',route/'timeline.json',
        candidate/'manifest.json',candidate/'native-cpu.sfc']
    sources.update({str(p):sha(p) for p in paths})
    report=dict(timing=cost['cases'],same_state=results,campaigns=details,
        known_stalls_recovered=all(all(r['gates'].values()) for r in results),
        route_complete=receipt['capture_complete'],release_ready=False,physical_verified=False,
        pop_free_verified=False,sources=sources,
        scope='Bounded copy optimization, not a completed interrupt fix. Both saved-state stalls persist. '
              'One-player route loses all power in the park and returns to room2; navigation times out. '
              'Changed enemy encounters are not performance ratios or proof of a gameplay regression.')
    table=''.join('<tr>'+''.join(f'<td>{v}</td>' for v in (r['case']['PPUADDR'],r['arms']['before']['clocks'],
        r['arms']['after']['clocks'],r['saved_clocks']))+'</tr>' for r in cost['cases'])
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Vertical PPU command cache</title>'
        '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:2em auto}'
        'a{color:cyan}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}figure{margin:0}'
        'img,audio{width:100%}img{image-rendering:pixelated}td,th{padding:8px;border:1px solid #567}</style>'
        '<h1>Vertical command copies:23–24% less measured CPU time</h1>'
        '<p>111 executed parent/candidate comparisons;90 independent CIRAM/dirty/counter/ABI checks. '
        'Same writes and command counts. Two20-byte fixture calls measured with neutral instruction observation.</p>'
        '<table><tr><th>PPU address(decimal)</th><th>Before clocks</th><th>After clocks</th><th>Saved</th></tr>'+table+'</table>'
        '<h2>Not ready for Rival</h2><p>Neither known saved-state stall is fixed. Independent running combat '
        'has two three-frame gaps; that is not causal proof because encounters differ. The full route fails '
        'after Alex loses all power and returns to the mall. No full-route scrolling/audio pass is claimed.</p>'
        '<div class="grid">'+''.join(failures)+'</div><h2>Unchanged stall cases</h2><div class="grid">'+
        ''.join(cards)+'</div><h2>Native replay audio</h2>'+''.join(audio)+
        '<p><a href="report.json">All measurements, failures, source hashes and limitations</a></p>')
    report['artifacts']={p.name:sha(p) for p in out.iterdir() if p.is_file()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(known_stalls_recovered=report['known_stalls_recovered'],route_complete=report['route_complete'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','oracle','timing','campaigns','route','control1','trial1','control2','trial2','out'):
        p.add_argument('--'+name,type=Path,required=True)
    review(**vars(p.parse_args()))
