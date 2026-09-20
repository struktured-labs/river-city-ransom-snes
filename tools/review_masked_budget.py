"""Retain same-state improvements and all independent combat failures."""
import argparse
import html
import json
from pathlib import Path
import shutil

from tools import combat_campaign as combat
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.review_retained_producer import authenticated_replay, compare
from tools.review_two_player_combat import stable_gaps, observed_play
from tools.two_player_combat import installed_policy, validate_ports


def ownership(ram):
    if len(ram)!=131072:raise ValueError('Missing full WRAM endpoint')
    pending=ram[0x1b80]
    scheduled,served,fallback=[int.from_bytes(ram[p:p+2],'little') for p in (0x1b81,0x1b83,0x1b85)]
    if pending not in (0,1) or (scheduled-served)&65535 != pending:
        raise ValueError('Producer ownership conservation failed')
    return dict(pending=pending,scheduled=scheduled,served=served,fallback=fallback,
                scope='Endpoint ownership only; no intermediate queue-deadline proof.')


def review(candidate,campaigns,control1,trial1,control2,trial2,oracle,out):
    if out.exists():raise ValueError('Fresh output required')
    proof=bound_report(oracle)
    if not proof['passed'] or proof['sources'].get(str(candidate/'native-cpu.sfc'))!=sha(candidate/'native-cpu.sfc'):
        raise ValueError('Wrong guard oracle')
    sources=dict(proof['sources']);episodes=[];cards=[];players=[]
    out.mkdir(parents=True)
    for index,(control,trial,event) in enumerate(((control1,trial1,2719),(control2,trial2,2726)),1):
        baseline,old=authenticated_replay(control);changed,new=authenticated_replay(trial)
        if (not baseline['passed'] or not changed['cross_rom_restore_verified'] or
                changed['trial']['resume_control']!=str(control) or
                changed['trial']['trial_rom_sha256']!=sha(candidate/'native-cpu.sfc') or
                (control/'initial.ram').read_bytes()!=(trial/'initial.ram').read_bytes() or
                baseline['initial_registers']!=changed['initial_registers']):
            raise ValueError('Unqualified/different starting state')
        result=compare(old,new,event);endpoints={}
        sources.update(baseline['sources']);sources.update(changed['sources'])
        for label,folder,rows in (('before',control,old),('after',trial,new)):
            sources[str(folder/'report.json')]=sha(folder/'report.json')
            endpoints[label]={stage:ownership((folder/(stage+'.ram')).read_bytes()) for stage in ('initial','final')}
            for stage in ('initial','final'):
                p=folder/(stage+'.ram');sources[str(p)]=sha(p)
            name=f'case{index}-{label}.wav';shutil.copy2(folder/'audio.wav',out/name)
            sources[str(folder/'audio.wav')]=sha(folder/'audio.wav')
            players.append(f'<p>Case {index} · {label}</p><audio controls src="{name}"></audio>')
        for a,b in list(zip(old,new))[:6]:
            for label,folder,row in (('before',control,a),('after',trial,b)):
                src=folder/row['frame_image'];name=f'case{index}-{label}-{row["frame"]}.png'
                if sha(src)!=row['frame_image_sha256']:raise ValueError('Changed source picture')
                shutil.copy2(src,out/name);sources[str(src)]=sha(src)
                cards.append(f'<figure><img src="{name}"><figcaption>Case {index} · {label} · frame {row["frame"]}</figcaption></figure>')
        episodes.append(dict(event=event,comparison=result,ownership=endpoints))
    details={}
    with installed_policy():
        for policy in combat.POLICIES:
            receipt,result,rows,normal=combat.verify_pair(campaigns,policy,'snes',candidate)
            ports=[]
            for kind in ('normal','observed'):
                folder=campaigns/f'{policy}-snes-{kind}'
                for name in ('combat-observer.json','two-player.json'):
                    binding=bound_report(folder/name);sources.update(binding['sources'])
                    sources[str(folder/name)]=sha(folder/name)
                records=json.loads((folder/'two-port-input.json').read_text())
                if validate_ports(records,rows,'snes')!=binding['delivery']:raise ValueError('Wrong ports')
                ports.append(records)
            if ports[0]!=ports[1]:raise ValueError('Observer changed port delivery')
            details[policy]=dict(frames=receipt['frames'],strict=result,stable=stable_gaps(result,rows,'snes'),
                                 play=observed_play(rows))
    paths=[Path(__file__),Path('tools/review_retained_producer.py'),Path('tools/review_two_player_combat.py'),
        Path('tools/audit_route_loop_cadence.py'),Path('tools/audit_main_display_latency.py'),oracle,
        candidate/'manifest.json',candidate/'native-cpu.sfc']
    sources.update({str(p):sha(p) for p in paths})
    result=dict(episodes=episodes,campaigns=details,source_bindings=sources,
        same_state_events_recovered=all(all(r['comparison']['gates'].values()) for r in episodes),
        strict_combat_passed=all(r['strict']['passed'] for r in details.values()),
        release_ready=False,physical_verified=False,pop_free_verified=False,worst_case_bound_proven=False,
        scope='Empirical shared120-line admission trial. Fixes two exact states; independent running combat still fails. '
              'Ownership checked at endpoints, not continuous deadlines. No hardware promotion or original-speed claim.')
    # Flat sources are compatible with the shared authenticated-report reader.
    result['sources']=result.pop('source_bindings')
    summary={p:r['stable']['frame_histogram'] for p,r in details.items()}
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Complete masked-path budget</title>'
        '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:2em auto}'
        'a{color:cyan}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}figure{margin:0}'
        'img,audio{width:100%}img{image-rendering:pixelated}pre{white-space:pre-wrap}</style>'
        '<h1>Two exact-state interrupt recoveries — not a release</h1>'
        '<p>Both known masked-over-VBlank cases finish one frame earlier. Before/after start with identical '
        '128KiB WRAM, CPU registers and actual two-port inputs. Same-ROM controls reproduce every replay byte.</p>'
        '<p>Only16 admission immediate bytes and cartridge checksum change. Line120 reserves the whole observed '
        'masked path, not just graphics preparation; this is empirical, not a universal worst-case bound.</p>'
        '<h2>Remaining failures</h2><p>Independent running combat still has three stable three-frame intervals '
        '(2237–2240,2250–2253,4315–4318). Encounters differ from the parent. They are not waived.</p><pre>'+
        html.escape(json.dumps(summary,indent=2))+'</pre><p>Rival untouched. Sound and renderer qualification '
        'are separate; these clips alone are not a pop-free verdict.</p><h2>Native unnormalized audio</h2>'+
        ''.join(players)+'<h2>Same-frame collages</h2><div class="grid">'+''.join(cards)+'</div>'
        '<p><a href="report.json">Every counter, campaign loop, failure and source hash</a></p>')
    result['artifacts']={p.name:sha(p) for p in out.iterdir() if p.is_file()}
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(same_state_events_recovered=result['same_state_events_recovered'],
                         strict_combat_passed=result['strict_combat_passed'],stable=summary)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','campaigns','control1','trial1','control2','trial2','oracle','out'):
        p.add_argument('--'+name,type=Path,required=True)
    review(**vars(p.parse_args()))
