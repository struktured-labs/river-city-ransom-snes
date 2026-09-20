"""Full-route original-NES actual pre-store to pixel-fetch latency, unaligned."""
import argparse
import csv
import json
from pathlib import Path

from tools.audit_display_cadence import cameras,rendering_enabled
from tools.audit_main_display_latency import bound_report,join
from tools.audit_route_loop_cadence import stable_room
from tools.audit_route_store_latency import segments
from tools.benchmark_report import sha,verify_capture


def audit(main,render,normal,out):
    proof=bound_report(main);receipt,rows=verify_capture(render);control,baseline=verify_capture(normal)
    for name,digest in receipt['route_store_observer']['sources'].items():
        if sha(Path(name))!=digest:raise ValueError('Route observer source changed: '+name)
    if (rows!=baseline or receipt['system']!='nes' or control['system']!='nes' or
            not receipt['capture_complete'] or not control['capture_complete'] or
            any(receipt[k]!=control[k] for k in ('rom_sha256','audio_sha256','scenario_sha256','frames')) or
            any(r['fault'] or r['input_requested']!=r['input_delivered'] for r in rows) or
            proof['sources'].get(str(render/'capture.json'))!=sha(render/'capture.json') or
            proof['sources'].get(str(normal/'capture.json'))!=sha(normal/'capture.json')):
        raise ValueError('Need complete neutral common original-NES control')
    wanted=[row['frame'] for i,row in enumerate(rows) if i and stable_room(rows[i-1:i+1]) is not None
            and rendering_enabled(row,'nes') and rendering_enabled(rows[i-1],'nes')]
    binding=receipt['render_scroll_trace'];trace=Path(binding['path'])
    if not wanted or sha(trace)!=binding['sha256'] or binding['first']>min(wanted) or binding['last']<max(wanted):
        raise ValueError('Missing complete renderer trace')
    with trace.open() as stream:rendered=cameras(csv.DictReader(stream),'nes',wanted)
    phases,excluded=segments(rows,rendered,'nes')
    result=join(proof['intervals'],phases)
    result.update(observer_neutral=True,rendered_frames=len(wanted),phases=phases,
        excluded_rendering_boundaries=excluded,
        room_events={str(room):sum(e['phase'].startswith(f'room{room}.') for e in result['events'])
                     for room in range(4)},release_ready=False,input_latency_verified=False,
        sources={**receipt['route_store_observer']['sources'],**{str(p):sha(p) for p in (Path(__file__),Path('tools/audit_main_display_latency.py'),
            Path('tools/audit_display_cadence.py'),Path('tools/audit_route_loop_cadence.py'),
            Path('tools/audit_route_store_latency.py'),Path('tools/audit_render_scroll.py'),
            Path('tools/benchmark_report.py'),render/'capture.json',normal/'capture.json',trace,main)}},
        scope='Original NES all stable room0..3 segments. Exact main start/input/pre-STA F6 '
              'chains; actual accumulator and high bit. Every 32 eight-pixel groups by 160 lines of '
              'fetch camera must be covered and agree. No fitted lag or event alignment. '
              'All unchanged/out-of-phase commits and rendering boundaries retained. '
              'Not completed-loop duration, equal-encounter cross-system speed or input latency.')
    out.mkdir(parents=True,exist_ok=False)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('rendered_frames','room_events','store_to_display',
        'start_to_display','missing_display')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('main','render','normal','out'):parser.add_argument('--'+name,type=Path,required=True)
    audit(**vars(parser.parse_args()))
