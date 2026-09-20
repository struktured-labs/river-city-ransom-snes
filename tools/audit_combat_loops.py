"""Combat regression: complete original loops, game ticks and physical frame starts."""
import argparse
from collections import Counter
from copy import deepcopy
import csv
import json
from pathlib import Path

from tools.audit_main_display_latency import bound_report
from tools.audit_main_store_latency import parse
from tools.audit_route_loop_cadence import nes_pair
from tools.benchmark_report import sha, verify_capture
from tools.nes_event_trace import validate

PHASES=('combat_approach','combat_take_hits','combat_counterattack',
        'combat_pause_request','combat_pause_wait','combat_resume_request','combat_resume_wait')


def measure(loops, rows):
    result={}
    for name in PHASES:
        frames=[r['frame'] for r in rows if r['phase']==name]
        if not frames or frames!=list(range(frames[0],frames[-1]+1)):
            raise ValueError('Missing/noncontiguous combat phase')
        chosen=[l for l in loops if l['start']['frame'] in range(frames[0],frames[-1]+1)]
        spans=[b['start']['frame']-a['start']['frame'] for a,b in zip(chosen,chosen[1:])]
        ticks=Counter(l['nmi_advances'] for l in chosen)
        # Final capture may stop with one incomplete iteration. Never silently
        # omit an interior loop; start spans must independently remain two.
        covered=len(chosen)>=len(frames)//2-1 and bool(spans)
        result[name]=dict(frames=[frames[0],frames[-1]],iterations=len(chosen),
            nmi_advances=dict(ticks),start_frame_spans=dict(Counter(spans)),
            passed=covered and set(ticks)=={2} and set(spans)=={2})
    selected=[l for l in loops if rows[l['start']['frame']-1]['phase'] in PHASES]
    other=[l for l in loops if rows[l['start']['frame']-1]['phase'] not in PHASES]
    return dict(passed=all(p['passed'] for p in result.values()),phases=result,
                iterations=selected,other_iterations=other,
                other_off_cadence=[l for l in other if l['nmi_advances']!=2])


def load(observed, normal, system, candidate):
    binding=bound_report(observed/'combat-observer.json')
    r,rows=verify_capture(observed);n,baseline=verify_capture(normal)
    if (r['system']!=system or binding['system']!=system or rows!=baseline or
            not r['capture_complete'] or not n['capture_complete'] or any(r[k]!=n[k] for k in
            ('rom_sha256','audio_sha256','frames','scenario_sha256'))):
        raise ValueError('Incomplete, different or nonneutral combat capture')
    with Path(binding['trace']).open() as f:records=list(csv.reader(f))
    if system=='snes':
        rom=candidate/'native-cpu.sfc';labels=candidate/'native_runtime.lbl'
        symbols={s.split()[2].lstrip('.'):int(s.split()[1],16) for s in labels.read_text().splitlines()}
        points={0:symbols['gameplay_iteration_start'],1:0xf282,
                2:symbols['camera_deferred_nmi_exit']+2,3:0xf2da}
        if binding['points']!={str(k):f'{v:04x}' for k,v in points.items()} or sha(rom)!=r['rom_sha256']:
            raise ValueError('Wrong SNES sites/cartridge')
        loops,censored=parse(records,points,len(rows),rom.read_bytes())
        for l in loops:l['nmi_advances']=(l['finish']['nmi']-l['start']['nmi'])&65535
    else:
        if binding['points']!={'0':'f27d','1':'f282','2':'f2da'}:raise ValueError('Wrong NES sites')
        validate(records,1,len(rows),len(rows),binding['points'])
        loops,censored=nes_pair(records)
    result=measure(loops,rows);result['censored']=censored
    # The trace itself is validated first. Mutate derived clocks/starts only
    # in copies; these are audit-sensitivity controls, not executed game faults.
    target=next(i for i,l in enumerate(loops) if rows[l['start']['frame']-1]['phase']=='combat_take_hits')+10
    mutants={}
    for name in ('three_ticks','physical_gap','missing_loop'):
        damaged=deepcopy(loops)
        if name=='three_ticks':damaged[target]['nmi_advances']=3
        elif name=='physical_gap':damaged[target]['start']['frame']+=1
        else:damaged.pop(target)
        mutants[name]=not measure(damaged,rows)['passed']
    if not all(mutants.values()):raise ValueError('Combat cadence mutation survived')
    result['derived_mutants_rejected']=mutants
    return r,result,binding


def audit(nes, normal_nes, snes, normal_snes, candidate, out):
    data={};sources={}
    for name,observed,normal in (('nes',nes,normal_nes),('snes',snes,normal_snes)):
        receipt,result,binding=load(observed,normal,name,candidate)
        data[name]=dict(receipt=receipt,result=result)
        sources.update(binding['sources'])
        for p in (observed/'combat-observer.json',normal/'capture.json'):
            sources[str(p)]=sha(p)
    if data['nes']['receipt']['scenario_sha256']!=data['snes']['receipt']['scenario_sha256']:
        raise ValueError('Different scenario')
    for p in map(Path,(__file__,'tools/audit_main_store_latency.py','tools/audit_route_loop_cadence.py',
                       'tools/nes_event_trace.py','tools/benchmark_report.py')):sources[str(p)]=sha(p)
    report=dict(passed=all(d['result']['passed'] for d in data.values()),observer_neutral=True,
        nes=data['nes']['result'],snes=data['snes']['result'],sources=sources,
        equal_work_full_game_verified=False,physical_combat_speed_verified=False,
        scope='Identical phase-based input policy on independent NES/SNES encounters. Every '
              'complete loop starting in all seven combat/pause/resume phases retained, including '
              'paused and hit states. Two game ticks AND two physical-frame start spans required. '
              'Startup/loading loops and incomplete boundaries retained separately, not waived '
              'as gameplay passes. Mutations test the audit, not the executed ROM.')
    out.mkdir(parents=True,exist_ok=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'],nes=report['nes']['phases'],snes=report['snes']['phases']),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('nes','normal-nes','snes','normal-snes','candidate','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
