"""Bind a known 1/3-frame scrolling stutter to exact camera-store instructions."""
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


def spacing(events, variable_producer=False):
    intervals=[b['frame']-a['frame'] for a,b in zip(events,events[1:])]
    if len(events)!=3 or (not variable_producer and intervals!=[2,2]):
        raise ValueError('Need three consecutive two-frame producer updates')
    if any(value<=0 for value in intervals):raise ValueError('Producer frames must increase')
    deltas=[((b['camera']-a['camera']+256)&511)-256 for a,b in zip(events,events[1:])]
    if deltas not in ([2,2],[-2,-2]):
        raise ValueError('Need uniform two-pixel producer steps')
    holds=[b['display_frame']-a['display_frame'] for a,b in zip(events,events[1:])]
    return dict(producer_frame_intervals=intervals,display_frame_intervals=holds,
                uniform_production=intervals==[2,2],
                presentation_tracks_producer=holds==intervals,
                uniform_presentation=holds==[2,2])


def first_new_display(rendered,frame,camera,last):
    """Do not attribute a repeated stationary position to a later store."""
    if frame-1 not in rendered:
        raise ValueError('Need preceding rendered frame for attribution')
    if camera in rendered[frame-1].values():
        raise ValueError('Camera was already displayed before selected store')
    for f in range(frame,last+1):
        if f not in rendered:raise ValueError('Missing rendered frame during attribution')
        values=set(rendered[f].values())
        if len(values)!=1:raise ValueError('Split camera during attribution')
        if values=={camera}:return f
    raise ValueError('Committed camera never displayed in window')


def audit(cpu,normal,raster,candidate,frames,out,variable_producer=False):
    receipt,rows=verify_capture(cpu);control,baseline=verify_capture(normal)
    if rows!=baseline or not receipt['capture_complete'] or any(receipt[k]!=control[k]
            for k in ('rom_sha256','scenario_sha256','audio_sha256','frames')):
        raise ValueError('CPU trace changed execution')
    rendered_rows,render_trace=neutral(raster,normal)
    if rendered_rows!=rows or sha(candidate/'native-cpu.sfc')!=receipt['rom_sha256']:
        raise ValueError('Different renderer or cartridge')
    labels={r.split()[2].lstrip('.'):int(r.split()[1],16) for r in (candidate/'native_runtime.lbl').read_text().splitlines()}
    entry=labels['camera_deferred_nmi_exit']
    image=(candidate/'native-cpu.sfc').read_bytes()
    if image[0x10000+entry:0x10000+entry+4]!=bytes.fromhex('e53b85f6'):
        raise ValueError('Unexpected camera store instruction')
    binding=receipt['instruction_trace'];trace=Path(binding['path'])
    if sha(trace)!=binding['sha256']:raise ValueError('Unbound instruction trace')
    with trace.open() as source:instructions=parse(csv.reader(source),binding['first'],binding['last'])
    commits=[r for r in instructions if r['pc']&65535==entry+2]
    if [r['frame'] for r in commits if min(frames)<=r['frame']<=max(frames)] != frames:
        raise ValueError('Intervening/missing producer update in selected sequence')
    window=range(min(frames),max(frames)+3)
    with render_trace.open() as source:rendered=scan(csv.DictReader(source),range(min(frames)-1,max(frames)+3))
    events=[]
    for frame in frames:
        hits=[r for r in commits if r['frame']==frame]
        if len(hits)!=1:raise ValueError('Ambiguous camera commit')
        hit=hits[0];ram=bytes.fromhex(rows[frame-1]['game_ram_hex'])
        if hit['opcode']!=0x85 or hit['a']&255!=ram[0xf6]:raise ValueError('Store differs from frame-end camera')
        # The high camera bit is stable across this selected street window.
        high=ram[0x3d]&1
        if any(bytes.fromhex(rows[f-1]['game_ram_hex'])[0x3d]&1 != high for f in window):
            raise ValueError('High camera bit changes in selected window')
        camera=(hit['a']&255)|(high<<8)
        visible=first_new_display(rendered,frame,camera,max(window))
        events.append(dict(frame=frame,line=hit['line'],cycle=hit['cycle'],clock=hit['clock'],
                           camera=camera,display_frame=visible))
    verdict=spacing(events,variable_producer)
    paths=[Path(__file__),Path('tools/audit_park_instructions.py'),Path('tools/audit_scroll_splits.py'),
           candidate/'native-cpu.sfc',candidate/'native_runtime.lbl',trace,render_trace,
           *[p/'capture.json' for p in (cpu,normal,raster)]]
    report=dict(**verdict,events=events,
        passed=verdict['uniform_presentation'] and verdict['uniform_production'],release_ready=False,
        sources={str(p):sha(p) for p in paths},
        scope='Fixed discovered counterexample, not a best-frame sample. Actual pre-STA-F6 A/beam '
              'and all160 rendered street lines establish producer/presentation spacing. '
              'High camera bit must stay constant, one store per selected frame required. '
              'A single case is not whole-game speed, general latency or acoustic certification.')
    out.mkdir(parents=True,exist_ok=False);cards=[]
    for frame in window:
        name=f'{frame}.png';shutil.copyfile(frame_path(normal,rows[frame-1]),out/name)
        cards.append(f'<figure><img src="{name}"><figcaption>Frame {frame}; displayed '
                     f'{sorted(set(rendered[frame].values()))}</figcaption></figure>')
    report['images']={p.name:sha(p) for p in out.glob('*.png')}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Known scroll pacing regression</title>'
        '<style>body{background:#101821;color:#eef;font:17px system-ui;max-width:1150px;margin:30px auto}'
        'a{color:#9df}.grid{display:grid;grid-template-columns:repeat(3,1fr)}figure{margin:8px}'
        'img{width:100%;image-rendering:pixelated}pre{white-space:pre-wrap}</style>'
        '<h1>Known pacing regression: '+('PASS' if report['passed'] else 'FAIL')+'</h1>'
        '<p>'+html.escape(report['scope'])+'</p><pre>'+html.escape(json.dumps(dict(events=events,**verdict),indent=2))+'</pre>'
        '<p><a href="report.json">Instruction and renderer evidence</a> · '
        '<a href="../display-cadence-651/">Complete park hold distributions versus NES</a></p>'
        '<div class="grid">'+''.join(cards)+'</div>')
    print(json.dumps(dict(events=events,**verdict),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('cpu','normal','raster','candidate','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--frames',type=int,nargs=3,required=True)
    p.add_argument('--variable-producer',action='store_true',
        help='Retain variable producer intervals as failure evidence, never as a speed pass')
    audit(**vars(p.parse_args()))
