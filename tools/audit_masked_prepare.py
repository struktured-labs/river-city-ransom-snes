"""Bind a retained graphics pass to a missed VBlank and delayed camera step."""
import argparse
import csv
import html
import json
from pathlib import Path
import shutil

from tools.audit_park_instructions import parse
from tools.audit_scroll_splits import neutral,scan
from tools.audit_scroll_publication import frame_path
from tools.benchmark_report import sha,verify_capture


def missed_vblank(masked,enabled,before,after):
    return (masked['line']<240 and enabled['frame']==masked['frame']+1 and enabled['line']<240
        and before['frame']==masked['frame']-1 and after['frame']==enabled['frame']
        and before['clock']<masked['clock']<enabled['clock']<after['clock'])


def audit(capture,normal,raster,candidate,frame,out):
    receipt,rows=verify_capture(capture);control,baseline=verify_capture(normal)
    if rows!=baseline or not receipt['capture_complete'] or any(receipt[k]!=control[k]
        for k in ('rom_sha256','scenario_sha256','audio_sha256','frames')):
        raise ValueError('Instruction observer changed execution')
    render_rows,render_trace=neutral(raster,normal)
    if render_rows!=rows:raise ValueError('Different rendered execution')
    rom=candidate/'native-cpu.sfc';program=rom.read_bytes()
    if sha(rom)!=receipt['rom_sha256']:raise ValueError('Wrong candidate cartridge')
    labels={r.split()[2].lstrip('.'):int(r.split()[1],16) for r in (candidate/'native_runtime.lbl').read_text().splitlines()}
    binding=receipt['instruction_trace'];trace=Path(binding['path']);spans=Path(receipt['span_trace']['path'])
    if sha(trace)!=binding['sha256'] or sha(spans)!=receipt['span_trace']['sha256']:raise ValueError('Changed bound trace')
    with trace.open() as stream:instructions=parse(csv.reader(stream),binding['first'],binding['last'])
    def runtime(r,address):return 0xc1<=r['pc']>>16<=0xc8 and r['pc']&65535==address
    hits=[i for i,r in enumerate(instructions) if r['frame']==frame and runtime(r,labels['second_tick_prepare_service'])]
    if len(hits)!=1:raise ValueError('Ambiguous retained producer service')
    begin=hits[0]
    def opcode(r,wanted):
        offset=r['pc']&0x3fffff
        return r['opcode']==wanted[0] and program[offset:offset+len(wanted)]==wanted
    prior=[i for i,r in enumerate(instructions[:begin]) if opcode(r,b'\x9c\x00\x42')]
    if not prior:raise ValueError('Missing actual NMI mask store')
    mask_index=prior[-1]
    enables=[i for i in range(begin,len(instructions)) if runtime(instructions[i],labels['camera_deferred_nmi_enable']+5)]
    if not enables:raise ValueError('Missing camera re-enable store')
    end=enables[0];enabled=instructions[end]
    if not opcode(enabled,b'\x8d\x00\x42') or not enabled['a']&0x80:raise ValueError('NMI not actually enabled at expected instruction')
    for r in instructions[mask_index+1:end]:
        if opcode(r,b'\x8d\x00\x42') and r['a']&0x80:raise ValueError('NMI enabled inside claimed masked interval')
    with spans.open() as stream:events=list(csv.reader(stream))
    if any(len(r)!=16 for r in events):raise ValueError('Malformed span event')
    nmis=[dict(frame=int(r[1]),line=int(r[2]),cycle=int(r[3]),clock=int(r[4])) for r in events if r[0]=='0']
    masked=instructions[mask_index];service=instructions[begin]
    before=[r for r in nmis if r['clock']<masked['clock']]
    after=[r for r in nmis if r['clock']>enabled['clock']]
    if not before or not after or any(masked['clock']<=r['clock']<=enabled['clock'] for r in nmis):
        raise ValueError('Incomplete or contradictory NMI observation')
    bridges=[r for r in events if r[0]=='6' and service['clock']<=int(r[4])<=enabled['clock']]
    if len(bridges)!=1:raise ValueError('Missing/ambiguous actual graphics bridge')
    window=range(frame-1,frame+6)
    with render_trace.open() as stream:rendered=scan(csv.DictReader(stream),window)
    if any(len(set(v.values()))!=1 for v in rendered.values()):raise ValueError('Split renderer cannot represent one camera')
    cameras=[dict(frame=f,camera=next(iter(rendered[f].values()))) for f in window]
    stores=[{k:r[k] for k in ('frame','line','cycle','clock','a')} for r in instructions
        if r['frame'] in window and runtime(r,labels['camera_deferred_nmi_exit']+2)]
    problem=missed_vblank(masked,enabled,before[-1],after[0])
    if not problem:raise ValueError('Selected case does not establish masked-over-VBlank failure')
    short=lambda r:{k:r[k] for k in ('frame','line','cycle','clock')}
    paths=[Path(__file__),Path('tools/audit_park_instructions.py'),Path('tools/audit_scroll_splits.py'),
        Path('tools/audit_scroll_publication.py'),Path('tools/benchmark_report.py'),rom,
        candidate/'native_runtime.lbl',trace,spans,render_trace,
        *[p/'capture.json' for p in (capture,normal,raster)]]
    report=dict(passed=False,release_ready=False,observer_neutral=True,
        masked=short(masked),service=short(service),enabled=short(enabled),
        masked_clocks=enabled['clock']-masked['clock'],nmi_before=before[-1],nmi_after=after[0],
        masked_across_entire_vblank=problem,camera_stores=stores,rendered_cameras=cameras,
        sources={str(p):sha(p) for p in paths},
        scope='Actual NMITIMEN mask/re-enable instructions, one observed graphics bridge, hardware NMI gap and every rendered street line. '
        'Fixed failing case, not every stutter, equal-work gameplay speed or acoustic certification.')
    out.mkdir(parents=True,exist_ok=False);cards=[]
    for r in cameras:
        name=f'frame-{r["frame"]}.png';shutil.copyfile(frame_path(normal,rows[r['frame']-1]),out/name)
        cards.append(f'<figure><img src="{name}"><figcaption>Frame {r["frame"]}; camera {r["camera"]}</figcaption></figure>')
    report['images']={p.name:sha(p) for p in out.glob('*.png')}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    summary={k:v for k,v in report.items() if k not in ('sources','images','scope')}
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Missed VBlank during graphics preparation</title>'
        '<style>body{background:#101821;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}a{color:#9df}'
        '.grid{display:grid;grid-template-columns:repeat(3,1fr)}figure{margin:8px}img{width:100%;image-rendering:pixelated}pre{white-space:pre-wrap}</style>'
        '<h1>Confirmed missed-VBlank regression</h1><p>'+html.escape(report['scope'])+'</p><p><a href="report.json">Bound evidence</a></p>'
        '<pre>'+html.escape(json.dumps(summary,indent=2))+'</pre><div class="grid">'+''.join(cards)+'</div>')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('capture','normal','raster','candidate','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--frame',type=int,required=True)
    audit(**vars(p.parse_args()))
