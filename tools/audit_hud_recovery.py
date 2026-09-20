"""Two source-bound HUD deadlines plus actual final palette execution, with real negatives."""
import argparse
import csv
import json
from pathlib import Path
from tools.audit_main_display_latency import bound_report
from tools.audit_hud_final_budget import decode, measure
from tools.benchmark_report import sha, verify_capture
from tools.capture_sprite_prefix import installed_prefix

ROOT=Path('build/overflow-3526')


def audit(out):
    if out.exists():raise ValueError('Fresh output required')
    sources={}; records={}
    def bind(path):
        r=bound_report(path);sources.update(r['sources']);sources[str(path)]=sha(path);return r
    parent=bind(ROOT/'boundary-video-parent-3741/publication-state.json')
    with installed_prefix('right_08'):
        _,baseline=verify_capture(Path(parent['normal']))
    for name,state,trace in (
        ('search_only','consumer-suffix-state-3757','consumer-suffix-instructions-3759'),
        ('late_rows_no_stop','suffix-row-budget-state-3762','suffix-row-budget-instructions-3763'),
        ('postrow_stop','postrow-stop-state-3767','postrow-stop-instructions-3766')):
        p=bind(ROOT/state/'publication-state.json');t=bind(ROOT/trace/'service-instructions.json')
        if not p['observer_neutral'] or not t['observer_neutral']:
            raise ValueError('Nonneutral observer')
        rom=Path(p['candidate'])/'native-cpu.sfc'
        if t['sources'].get(str(rom))!=sha(rom):raise ValueError('Different state/trace cartridge')
        with installed_prefix('right_08'):
            receipt,rows=verify_capture(Path(p['normal']))
        selected={2472:[],2484:[]}
        with Path(t['trace']).open() as stream:
            for raw in csv.reader(stream):
                if int(raw[0]) in selected:selected[int(raw[0])].append(decode(raw))
        cases=[]
        for f,ins in selected.items():
            old=Path(parent['samples'][str(f)]['path']).read_bytes()
            staged=Path(p['samples'][str(f)]['path']).read_bytes()
            published=Path(p['samples'][str(f+1)]['path']).read_bytes()
            source_equal=old[0x12000:0x13000]==staged[0x12000:0x13000]
            ready=bool(staged[0x1d02]&2)
            target=old[0x3080:0x30c0]
            stage_equal=target==staged[0x3080:0x30c0]
            actual=published[0x24080:0x240c0]
            displayed=rows[f]['video_sha256']==baseline[f]['video_sha256']
            final=None;error=None
            try:final=measure(ins)
            except ValueError as e:error=str(e)
            gates=dict(equal_original_source=source_equal,ready=ready,equal_staged_row=stage_equal,
                       row_in_vram_next_frame=actual==target,whole_picture_matches_parent=displayed,
                       final_palette_executed=final is not None)
            cases.append(dict(staged_frame=f,displayed_frame=f+1,gates=gates,final=final,
                              final_failure=error,staged_hex=target.hex(),actual_hex=actual.hex()))
        differences={k:[a['frame'] for a,b in zip(baseline,rows) if a[k]!=b[k]]
                     for k in ('probe_052b','input_requested','input_delivered','video_sha256')}
        differences['camera']=[a['frame'] for a,b in zip(baseline,rows)
                               if a['native']['logical_camera_x']!=b['native']['logical_camera_x']]
        passed=all(all(c['gates'].values()) for c in cases) and all(
            not differences[k] for k in differences if k!='video_sha256') and len(rows)==len(baseline)
        records[name]=dict(rom_sha256=receipt['rom_sha256'],passed=passed,cases=cases,
                           differences=differences,frames=len(rows))
    if records['search_only']['passed'] or records['late_rows_no_stop']['passed']:
        raise ValueError('Real failing control escaped symptom/tradeoff gate')
    if not records['postrow_stop']['passed']:raise ValueError('Combined HUD/final gate failed')
    for p in (Path(__file__),Path('tools/audit_hud_final_budget.py')):sources[str(p)]=sha(p)
    report=dict(sources=sources,variants=records,passed=True,release_ready=False,
                scope=__doc__+' Two events only; complete prefix counters/inputs/camera and all image '
                'differences retained. Not broad renderer/DMA/HDMA or acoustic qualification.')
    out.mkdir(parents=True)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:dict(passed=v['passed'],changed_images=len(v['differences']['video_sha256']))
                      for k,v in records.items()}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    audit(**vars(parser.parse_args()))
