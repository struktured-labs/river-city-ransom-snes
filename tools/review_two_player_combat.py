"""Two-player input/control evidence and retained combat cadence failures."""
import argparse
from collections import Counter
import html
import json
from pathlib import Path
import shutil

from tools import combat_campaign as combat
from tools.audit_main_display_latency import bound_report
from tools.audit_route_loop_cadence import stable_room
from tools.benchmark_report import sha
from tools.two_player_combat import installed_policy, validate_ports


def observed_play(rows):
    selected=[r for r in rows if r['phase']=='combat_approach'][-32:]
    if len(selected)!=32:
        raise ValueError('Missing controlled right-input observation')
    samples=[bytes.fromhex(r['game_ram_hex']) for r in selected]
    if any(len(r)!=2048 or r[0xf0:0xf2]!=b'\x01\x01' for r in samples):
        raise ValueError('Original game did not retain Right for both controllers')
    # Retain original actor coordinates, rather than infer activity from a name.
    positions=[dict(frame=row['frame'],p1=r[0x388]+256*r[0x390],
        p2=r[0x389]+256*r[0x391]) for row,r in zip(selected,samples)]
    if any(positions[-1][key]<=positions[0][key] for key in ('p1','p2')):
        raise ValueError('Missing observed movement of a player')
    return dict(frames=[r['frame'] for r in selected],positions=positions,
        scope='Both original held-input bytes are Right across32 frames; both actor coordinates advance. '
              'Not a matched-encounter speed ratio or comprehensive controller test.')


def stable_gaps(result,rows,system):
    loops=sorted(result['iterations']+result['other_iterations'],key=lambda l:l['start']['clock'])
    selected=[]
    for a,b in zip(loops,loops[1:]):
        first,last=a['start']['frame'],b['start']['frame']
        room=stable_room(rows[first-1:last])
        if room is None:
            continue
        clocks=b['start']['clock']-a['start']['clock']
        selected.append(dict(first=first,last=last,frames=last-first,room=room,
            elapsed_core_clocks=clocks,completed_game_ticks=a['nmi_advances'],
            native_start_ticks=None if system=='nes' else (b['start']['nmi']-a['start']['nmi'])&65535,
            start=a['start'],finish=a['finish'],next_start=b['start'],commit=a.get('commit')))
    return dict(intervals=len(selected),frame_histogram=dict(Counter(x['frames'] for x in selected)),
        longer_than_two=[x for x in selected if x['frames']>2],
        scope='Stable original-game predicates over every intervening captured frame; room loads and pauses excluded here, '
              'but remain in the full strict combat results. NES clocks and SNES clocks have different units.')


def review(root,candidate,out):
    if out.exists():raise ValueError('Fresh output required')
    details={};sources={};cards=[];out.mkdir(parents=True)
    with installed_policy():
        for policy in combat.POLICIES:
            details[policy]={};receipts=[]
            for system in ('nes','snes'):
                receipt,result,rows,normal=combat.verify_pair(root,policy,system,candidate)
                receipts.append(receipt)
                inputs=[]
                for kind in ('normal','observed'):
                    folder=root/f'{policy}-{system}-{kind}'
                    proof=bound_report(folder/'two-player.json')
                    if (proof['system'],proof['policy'],proof['observed'])!=(system,policy,kind=='observed'):
                        raise ValueError('Wrong two-player capture identity')
                    record=json.loads((folder/'two-port-input.json').read_text())
                    if validate_ports(record,rows,system)!=proof['delivery']:
                        raise ValueError('Altered port summary')
                    inputs.append(record)
                    observer=bound_report(folder/'combat-observer.json')
                    sources.update(observer['sources']);sources.update(proof['sources'])
                    sources[str(folder/'two-player.json')]=sha(folder/'two-player.json')
                if inputs[0]!=inputs[1]:raise ValueError('Observation changed actual port delivery')
                play=observed_play(rows);gaps=stable_gaps(result,rows,system)
                details[policy][system]=dict(strict_two_frame=result,stable=gaps,play=play,
                    frames=receipt['frames'],delivery=proof['delivery'])
                label=policy+'-'+system
                shutil.copy2(normal/'audio.wav',out/(label+'.wav'))
                pictures=[]
                for phase in ('idle','combat_take_hits','combat_counterattack','combat_pause_wait'):
                    src=normal/(phase+'.png');name=label+'-'+phase+'.png'
                    shutil.copy2(src,out/name);sources[str(src)]=sha(src)
                    pictures.append('<figure><img src="'+name+'"><figcaption>'+phase+'</figcaption></figure>')
                table=''.join('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in
                    (phase,v['iterations'],v['nmi_advances'],v['start_frame_spans'],v['passed']))+'</tr>'
                    for phase,v in result['phases'].items())
                cards.append('<section><h2>'+label+'</h2><p>Strict two-frame gate: '+str(result['passed'])+
                    '. Stable start intervals: '+html.escape(str(gaps['frame_histogram']))+
                    '. Both controllers consumed and both players moved.</p><div class="grid">'+''.join(pictures)+
                    '</div><audio controls preload="none" src="'+label+'.wav"></audio>'
                    '<table><tr><th>Input phase</th><th>Loops</th><th>Ticks</th><th>Start spacing</th><th>Strict pass</th></tr>'+
                    table+'</table></section>')
            if receipts[0]['scenario_sha256']!=receipts[1]['scenario_sha256']:
                raise ValueError('Different NES/SNES requested policy')
    paths=[Path(__file__),Path('tools/two_player_combat.py'),Path('tools/combat_campaign.py'),
        Path('tools/audit_combat_loops.py'),Path('tools/audit_main_store_latency.py'),
        Path('tools/audit_route_loop_cadence.py'),Path('tools/nes_event_trace.py'),
        Path('tools/benchmark_report.py'),Path('tests/test_two_player_combat.py'),
        candidate/'manifest.json',candidate/'native-cpu.sfc']
    sources.update({str(p):sha(p) for p in paths})
    report=dict(campaigns=details,sources=sources,observer_neutral=True,
        strict_two_frame_passed=all(r['strict_two_frame']['passed'] for p in details.values() for r in p.values()),
        original_speed_parity_verified=False,physical_verified=False,pop_free_verified=False,release_ready=False,
        scope='Independent ordinary two-player encounters, each with same-core normal/observer full timeline/PCM controls. '
              'Strict one-player-style two-frame failures are retained, including on the NES. '
              'Input policy equality is not enemy/CPU workload equality or proof of a port-only slowdown.')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Two-player combat regression</title>'
        '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1200px;margin:2em auto}'
        'a{color:cyan}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}img{width:100%;image-rendering:pixelated}'
        'figure{margin:0}audio{width:100%}td,th{border:1px solid #567;padding:6px}section{margin:3em 0}</style>'
        '<h1>Two-player combat: original NES vs current SNES</h1><p>No memory patches or saves. P1 selects2P; both pads receive '
        'ordinary attack/direction inputs. Original game input bytes and both moving actor coordinates are checked.</p>'
        '<p><strong>This is not a full-speed pass.</strong> The NES itself has three-frame updates in these encounters. '
        'SNES stable three-frame intervals require instruction-level investigation; raw failures and all loops are retained. '
        'Native audio is supplied for audit, not graded pop-free. Rival is untouched by these tests.</p>'
        '<p><a href="report.json">Every loop, interval, input proof and source hash</a></p>'+''.join(cards))
    report['artifacts']={p.name:sha(p) for p in out.iterdir() if p.is_file()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({p:{s:dict(strict=r['strict_two_frame']['passed'],stable=r['stable']['frame_histogram'])
                          for s,r in group.items()} for p,group in details.items()}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('root','candidate','out'):p.add_argument('--'+name,type=Path,required=True)
    review(**vars(p.parse_args()))
