"""Check all four rooms' main loops and park rendering in the driver candidate."""
import argparse
import csv
import json
from pathlib import Path

from tools.audit_main_store_latency import parse
from tools.audit_route_loop_cadence import measure
from tools.audit_display_cadence import observe
from tools.audit_uniform_holds import summarize
from tools.benchmark_report import sha,verify_capture


def audit(candidate,normal,main,render,out):
    n,baseline=verify_capture(normal);m,rows=verify_capture(main)
    if not n['capture_complete'] or not m['capture_complete'] or baseline!=rows or any(
            n[k]!=m[k] for k in ('rom_sha256','audio_sha256','frames','scenario_sha256')):
        raise ValueError('Non-neutral main observer')
    binding=m['main_store_observer'];trace=Path(binding['trace']['path'])
    for p,digest in binding['sources'].items():
        if sha(Path(p))!=digest:raise ValueError('Changed main source: '+p)
    if sha(trace)!=binding['trace']['sha256']:raise ValueError('Changed main trace')
    labels=candidate/'native_runtime.lbl';rom=candidate/'native-cpu.sfc'
    if sha(rom)!=n['rom_sha256']:raise ValueError('Different ROM')
    symbols={s.split()[2].lstrip('.'):int(s.split()[1],16) for s in labels.read_text().splitlines()}
    points={0:symbols['gameplay_iteration_start'],1:0xf282,
        2:symbols['camera_deferred_nmi_exit']+2,3:0xf2da}
    if binding['points']!={str(k):f'{v:04x}' for k,v in points.items()}:raise ValueError('Different main sites')
    with trace.open() as f:loops,outside=parse(csv.reader(f),points,n['frames'],rom.read_bytes())
    for loop in loops:loop['nmi_advances']=(loop['finish']['nmi']-loop['start']['nmi'])&65535
    main_result=measure(loops,rows)
    rendered=observe(render,normal,'snes')
    holds={p:summarize(r) for p,r in rendered['phases'].items()}
    passed=main_result['sampled_two_tick_cadence'] and not any(r['short_irregular'] for r in holds.values())
    # Deliberate clock/camera corruptions prove both gates fail in this dataset.
    bad=json.loads(json.dumps(loops));first=next(v['iterations'][0]['start']['frame'] for v in main_result['rooms'].values())
    next(r for r in bad if r['start']['frame']==first)['nmi_advances']=3
    loop_mutant=not measure(bad,rows)['sampled_two_tick_cadence']
    if not loop_mutant:raise ValueError('Three-tick iteration mutation survived')
    paths=[Path(__file__),Path('tools/audit_main_store_latency.py'),Path('tools/audit_route_loop_cadence.py'),
        Path('tools/audit_display_cadence.py'),Path('tools/audit_uniform_holds.py'),Path('tools/benchmark_report.py'),
        normal/'capture.json',main/'capture.json',labels,rom,trace]
    result=dict(passed=passed,observer_neutral=True,main=main_result,censored=outside,
        rendering=rendered,holds=holds,three_tick_mutant_rejected=loop_mutant,
        sources={**binding['sources'],**rendered['sources'],**{str(p):sha(p) for p in paths}},
        release_ready=False,equal_work_original_speed_verified=False,
        scope='All four sampled rooms: complete main/input/finish chains, two NMI ticks per stable '
        'iteration and consecutive stable starts. Full park background renderer coverage; all '
        'stops and censored boundaries retained. Not equal-work full-game NES or physical speed.')
    out.mkdir(parents=True,exist_ok=False);(out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=passed,rooms={k:dict(iterations=len(v['iterations']),nmi=v['nmi_advances'],
        starts=v['start_frame_spans']) for k,v in main_result['rooms'].items()},
        holds={p:dict(histogram=r['histogram'],short_irregular=len(r['short_irregular'])) for p,r in holds.items()})))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','normal','main','render','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
