"""Same-state retained-NMI recovery and independent two-player regression evidence."""
import argparse
from collections import Counter
import html
import json
from pathlib import Path
import shutil

from tools import combat_campaign as combat
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.review_two_player_combat import observed_play, stable_gaps
from tools.two_player_combat import installed_policy, validate_ports


def counters(row):
    game = bytes.fromhex(row['game_ram_hex'])
    native = bytes.fromhex(row['native_ram_hex'])
    if len(game) != 2048 or len(native) != 1024:
        raise ValueError('Incomplete frame-end RAM')
    return dict(frame=row['frame'], nmi=int.from_bytes(native[4:6], 'little'),
                completed=game[0x52b], camera=game[0xf6]+((game[0x3d]&1)<<8))


def compare(old, new, event):
    if not old or [r['frame'] for r in old] != [r['frame'] for r in new]:
        raise ValueError('Different replay windows')
    if any(b['frame'] != a['frame']+1 for a,b in zip(old, old[1:])):
        raise ValueError('Missing replay frame')
    series = []
    for a,b in zip(old,new):
        if (a['input_requested'] != b['input_requested'] or
                a['input_delivered'] != b['input_delivered']):
            raise ValueError('Different replay input')
        series.append(dict(frame=a['frame'], before=counters(a), after=counters(b),
                           same_picture=a['video_sha256']==b['video_sha256'],
                           same_pcm=a['audio_sha256']==b['audio_sha256']))
    index = next((i for i,r in enumerate(series) if r['frame']==event), None)
    if index is None or index == 0 or index+1 == len(series):
        raise ValueError('Missing event neighbors')
    previous, current, following = series[index-1:index+2]
    def delta(label, key):
        return (current[label][key]-previous[label][key]) % (65536 if key=='nmi' else 256)
    gates = dict(old_interrupt_did_not_advance=delta('before','nmi')==0,
        new_interrupt_advanced_once=delta('after','nmi')==1,
        old_completion_did_not_advance=delta('before','completed')==0,
        new_completion_advanced_once=delta('after','completed')==1,
        old_completion_arrived_next_frame=(following['before']['completed']-
                                          current['before']['completed'])%256==1,
        same_picture_through_following_frame=all(r['same_picture'] for r in series[:index+2]))
    return dict(gates=gates, series=series,
        scope='Frame-end counters only. The known traced missed VBlank is the nominated event; '
              'other zero counter deltas are retained, not automatically classified as missed edges. '
              'Same initial state does not guarantee equal later enemy work after timing diverges.')


def authenticated_replay(folder):
    report = bound_report(folder/'report.json')
    for name,digest in report['artifacts'].items():
        if sha(folder/name) != digest:
            raise ValueError('Changed replay artifact: '+name)
    if not report['two_player'] or not report['same_state_comparison_valid']:
        raise ValueError('Unqualified replay')
    return report, json.loads((folder/'timeline.json').read_text())


def review(parent, candidate, baseline, campaigns, control, trial, oracle, event, out):
    if out.exists():
        raise ValueError('Fresh output required')
    before, old = authenticated_replay(control)
    after, new = authenticated_replay(trial)
    proof = bound_report(oracle)
    if (not before['passed'] or not after['cross_rom_restore_verified'] or
            after['trial']['resume_control'] != str(control) or
            after['trial']['trial_rom_sha256'] != sha(candidate/'native-cpu.sfc') or
            after['trial']['parent_rom_sha256'] != sha(parent/'native-cpu.sfc') or
            (control/'initial.ram').read_bytes() != (trial/'initial.ram').read_bytes() or
            not proof['passed'] or proof['sources'].get(str(candidate/'native-cpu.sfc')) !=
            sha(candidate/'native-cpu.sfc')):
        raise ValueError('Different or unqualified patch/control/oracle')
    same_state = compare(old,new,event)
    sources = {**before['sources'], **after['sources'], **proof['sources']}
    summaries = {}
    with installed_policy():
        for policy in combat.POLICIES:
            summaries[policy] = {}
            for label,root,rom in (('before',baseline,parent),('after',campaigns,candidate)):
                receipt,result,rows,normal = combat.verify_pair(root,policy,'snes',rom)
                records = []
                for kind in ('normal','observed'):
                    folder = root/f'{policy}-snes-{kind}'
                    binding = bound_report(folder/'two-player.json')
                    record = json.loads((folder/'two-port-input.json').read_text())
                    if validate_ports(record,rows,'snes') != binding['delivery']:
                        raise ValueError('Wrong controller delivery summary')
                    records.append(record)
                    sources.update(binding['sources'])
                    sources[str(folder/'two-player.json')] = sha(folder/'two-player.json')
                    observer = bound_report(folder/'combat-observer.json')
                    sources.update(observer['sources'])
                    sources[str(folder/'combat-observer.json')] = sha(folder/'combat-observer.json')
                if records[0] != records[1]:
                    raise ValueError('Observer changed port delivery')
                summaries[policy][label] = dict(frames=receipt['frames'],
                    stable=stable_gaps(result,rows,'snes'),strict_two_frame=result,
                    play=observed_play(rows))
    paths = [Path(__file__),Path('tools/review_two_player_combat.py'),
        Path('tools/audit_route_loop_cadence.py'),Path('tools/audit_main_display_latency.py'),
        control/'report.json',trial/'report.json',oracle]
    sources.update({str(p):sha(p) for p in paths})
    out.mkdir(parents=True)
    cards = []
    for a,b in zip(old,new):
        if not event-3 <= a['frame'] <= event+4:
            continue
        for label,folder,row in (('before',control,a),('after',trial,b)):
            src = folder/row['frame_image']; name=f'{label}-{row["frame"]}.png'
            if sha(src) != row['frame_image_sha256']:
                raise ValueError('Changed screenshot')
            shutil.copy2(src,out/name);sources[str(src)]=sha(src)
            cards.append(f'<figure><img src="{name}"><figcaption>{label} · frame {row["frame"]}'
                         f' · NMI {counters(row)["nmi"]}</figcaption></figure>')
    for label,folder in (('before',control),('after',trial)):
        shutil.copy2(folder/'audio.wav',out/(label+'.wav'))
        sources[str(folder/'audio.wav')] = sha(folder/'audio.wav')
    summary = {p:{s:r['stable']['frame_histogram'] for s,r in group.items()}
               for p,group in summaries.items()}
    report = dict(same_state=same_state,campaigns=summaries,
        event_recovered=all(same_state['gates'].values()),
        oracle_cases=len(proof['cases']),oracle_mutants=len(proof['mutants']),
        release_ready=False,physical_verified=False,pop_free_verified=False,
        original_speed_parity_verified=False,sources=sources,
        scope='Offline patch. Same-ROM restore is exact; cross-ROM differences are expected and retained. '
              'Independent campaign counts are not matched-encounter performance ratios. '
              'Three-frame intervals remain. No audio fidelity or rendering correctness waiver.')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8">'
        '<title>Retained interrupt recovery</title><style>body{background:#101820;color:#eef;'
        'font:17px system-ui;max-width:1100px;margin:2em auto}a{color:cyan}.grid{display:grid;'
        'grid-template-columns:repeat(2,1fr);gap:12px}figure{margin:0}img,audio{width:100%}'
        'img{image-rendering:pixelated}pre{white-space:pre-wrap}</style>'
        '<h1>One missed combat interrupt recovered</h1><p>Offline only; Rival unchanged. '
        'The exact same saved state and inputs finish the affected update on frame 2292 '
        'instead of 2293. First five replayed pictures match; later execution diverges.</p>'
        '<p>The late camera guard used to be bypassed by the retained interrupt fallback, '
        'which started two graphics passes with interrupts masked. The trial leaves pending '
        'work owned for the next real interrupt.</p><h2>Independent combat stress</h2><pre>'+
        html.escape(json.dumps(summary,indent=2))+'</pre><p>Stable update spacing histograms, '
        'not equal-work speed ratios. All strict failures and remaining three-frame gaps are retained.</p>'
        '<h2>Same-state native audio</h2><p>Before</p><audio controls src="before.wav"></audio>'
        '<p>After</p><audio controls src="after.wav"></audio><p>Unnormalized emulator output; '
        'different later gameplay can legitimately change sound. Not graded pop-free.</p>'
        '<h2>Same-frame comparison</h2><div class="grid">'+''.join(cards)+'</div>'
        '<p><a href="report.json">Counters, all loops, failures and source hashes</a></p>')
    report['artifacts'] = {p.name:sha(p) for p in out.iterdir() if p.is_file()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(event_recovered=report['event_recovered'],campaigns=summary)))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','candidate','baseline','campaigns','control','trial','oracle','out'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--event',type=int,default=2292)
    review(**vars(p.parse_args()))
