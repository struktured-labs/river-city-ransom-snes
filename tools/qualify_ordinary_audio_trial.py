"""Revalidate combat, rendered cadence and the status/pause gates for the audio trial."""
import argparse
import json
from pathlib import Path

from tools.audit_busy_combat import measure
from tools.audit_display_cadence import observe
from tools.audit_main_display_latency import bound_report
from tools.audit_uniform_holds import summarize
from tools.benchmark_report import sha, verify_capture
from tools.check_present_status import compare as status_compare
from tools.combat_campaign import verify_pair
from tools.review_retained_producer import authenticated_replay, compare, counters
from tools.two_player_combat import installed_policy


def audit(candidate,campaign,renderer,normal,render_audit,status,pause,audio,earlier,earlier_control,newer,newer_control,out):
    if out.exists():raise ValueError('Fresh output required')
    with installed_policy():
        receipt,strict,rows,_=verify_pair(campaign,'running-jumps','snes',candidate)
    busy=measure(strict,rows)
    cadence=observe(renderer,normal,'snes')
    holds={k:summarize(v) for k,v in cadence['phases'].items()}
    proofs={name:bound_report(root/'report.json') for name,root in
            (('renderer',render_audit),('pause',pause),('audio',audio))}
    sources=dict(cadence['sources'])
    status_report=json.loads((status/'report.json').read_text())
    status_paths=[]
    for name in ('nes','snes'):
        entry=status_report['captures'][name];root=Path(entry['path'])
        r,_=verify_capture(root)
        if sha(root/'capture.json')!=entry['sha256'] or r['rom_sha256']!=entry['rom_sha256']:
            raise ValueError('Changed status capture')
        if name=='snes' and r['rom_sha256']!=receipt['rom_sha256']:
            raise ValueError('Different status cartridge')
        status_paths.append(root)
        sources.update({str(p):sha(p) for p in root.iterdir() if p.is_file()})
    if status_compare(*status_paths)!=status_report['phases']:
        raise ValueError('Changed status oracle result')
    proofs['status']={**status_report,'sources':{}}
    for name,root in (('renderer',render_audit),('status',status),('pause',pause),('audio',audio)):
        sources.update(proofs[name]['sources']);sources[str(root/'report.json')]=sha(root/'report.json')
    for kind in ('normal','observed'):
        root=campaign/f'running-jumps-snes-{kind}'
        for name in ('combat-observer.json','two-player.json'):
            p=root/name;sources.update(bound_report(p)['sources']);sources[str(p)]=sha(p)
        for p in (root/'timeline.json',root/'capture.json',root/'two-port-input.json'):
            sources[str(p)]=sha(p)
    for p in (Path(__file__),Path('tools/audit_busy_combat.py'),Path('tools/audit_display_cadence.py'),
        Path('tools/audit_uniform_holds.py'),Path('tools/combat_campaign.py'),Path('tools/two_player_combat.py'),
        Path('tools/check_status_regression.py'),Path('tools/check_present_status.py'),Path('tools/review_retained_producer.py'),
        candidate/'native-cpu.sfc',candidate/'manifest.json'):
        sources[str(p)]=sha(p)
    if cadence['rom_sha256']!=receipt['rom_sha256'] or proofs['audio']['arms']['trial']['rom_sha256']!=receipt['rom_sha256']:
        raise ValueError('Mixed candidate evidence')
    passed=all(p['passed'] for p in proofs.values()) and strict['passed'] and busy['passed'] and all(
        not h['short_irregular'] for h in holds.values())
    if any(proofs['audio']['arms'][name]['late_restarts'] for name in ('baseline','trial')):
        raise ValueError('Late DSP configuration on restart')
    replays={}
    for name,control,trial,event in (('earlier',earlier_control,earlier,2239),('newer',newer_control,newer,2250)):
        before,old=authenticated_replay(control);after,new=authenticated_replay(trial)
        if not before['passed'] or not after['cross_rom_restore_verified'] or (
                after['trial']['trial_rom_sha256']!=receipt['rom_sha256'] or
                after['trial']['resume_control']!=str(control) or
                (control/'initial.ram').read_bytes()!=(trial/'initial.ram').read_bytes()):
            raise ValueError('Wrong exact replay/control')
        detail=compare(old,new,event)
        if name=='earlier':
            replay_pass=all(detail['gates'].values())
        else:
            # This checkpoint's parent already counts the next NMI on2250;
            # the retained-body completion, not the NMI counter, is delayed.
            gates={k:v for k,v in detail['gates'].items() if k!='old_interrupt_did_not_advance'}
            gates['pictures_through_2252']=all(a['video_sha256']==b['video_sha256']
                for a,b in zip(old,new) if a['frame']<=2252)
            replay_pass=all(gates.values());detail['newer_recovery_gates']=gates
        passed=passed and replay_pass
        replays[name]=dict(passed=replay_pass,comparison=detail)
        for root,r in ((control,before),(trial,after)):
            sources.update(r['sources']);sources[str(root/'report.json')]=sha(root/'report.json')
            sources.update({str(root/p):h for p,h in r['artifacts'].items()})
    report=dict(passed=passed,rom_sha256=receipt['rom_sha256'],combat=dict(strict=strict,busy=busy),
        scrolling=holds,replays=replays,status_passed=proofs['status']['passed'],pause_passed=proofs['pause']['passed'],
        audio_stddev_reduction=proofs['audio']['completion_interval_stddev_reduction'],sources=sources,
        release_ready=False,physical_verified=False,pop_free_verified=False,
        remaining=['other three menu regressions','late-DMA fixture under new scheduling',
                   'broader original-NES speed comparison','physical Bluemage audio/video qualification'],
        scope=__doc__+' Fixed running-jump policy and park route only; not full-game or hardware certification.')
    out.mkdir(parents=True)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    for path,digest in sources.items():
        if sha(Path(path))!=digest:raise ValueError('Changed source: '+path)
    print(json.dumps(dict(passed=passed,combat_intervals=busy['intervals'],combat_histogram=busy['frame_histogram'],
        scroll={k:dict(histogram=v['histogram'],short_irregular=len(v['short_irregular']))for k,v in holds.items()},
        replays={k:v['passed'] for k,v in replays.items()},status=proofs['status']['passed'],pause=proofs['pause']['passed'])))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ('candidate','campaign','renderer','normal','render-audit','status','pause','audio',
              'earlier','earlier-control','newer','newer-control','out'):
        parser.add_argument('--'+k,type=Path,required=True)
    audit(**vars(parser.parse_args()))
