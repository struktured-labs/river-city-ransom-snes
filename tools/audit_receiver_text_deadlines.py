"""Separate source-phase changes from ready-row delays in receiver trial3934."""
import argparse
import csv
import html
import json
from pathlib import Path
import shutil

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha, verify_capture


def attribute(before, after, target):
    if not before or [r['frame'] for r in before] != [r['frame'] for r in after]:
        raise ValueError('Missing or unequal coverage')
    times = []
    for records in (before, after):
        arm = {}
        for key in ('source', 'prepared', 'vram'):
            if records[0][key] == target:
                raise ValueError('Left-censored generation')
            hits = [r['frame'] for r in records if r[key] == target]
            if not hits:
                raise ValueError('Right-censored generation')
            first = hits[0]
            if any(r[key] != target for r in records if r['frame'] >= first):
                raise ValueError('Multiple generations in selected window')
            arm[key] = first
        if not arm['source'] <= arm['prepared'] <= arm['vram']:
            raise ValueError('Invalid pipeline ordering')
        arm['prepare_lag'] = arm['prepared'] - arm['source']
        arm['publish_lag'] = arm['vram'] - arm['prepared']
        times.append(arm)
    a, b = times
    return dict(before=a, after=b, source_phase=b['source']-a['source'],
                prepare_lag_change=b['prepare_lag']-a['prepare_lag'],
                publish_lag_change=b['publish_lag']-a['publish_lag'],
                display_delay=b['vram']-a['vram'],
                equal_source_timeline=all(a['source']==b['source']
                                          for a,b in zip(before,after)))


def audit(before, after, parent_trace, trial_trace, parent_normal, trial_normal, out):
    if out.exists():
        raise ValueError('Fresh output required')
    paths = [Path(__file__), Path('tools/audit_main_display_latency.py'),
             Path('tools/benchmark_report.py'), Path('tests/test_receiver_text_deadlines.py')]
    sources = {str(p): sha(p) for p in paths}
    states = {}
    for arm, root in (('before',before),('after',after)):
        p = root/'publication-state.json'
        proof = bound_report(p)
        if not proof['observer_neutral']:
            raise ValueError('Non-neutral memory observation')
        sources.update(proof['sources']); sources[str(p)] = sha(p)
        states[arm] = {int(f):Path(v['path']).read_bytes() for f,v in proof['samples'].items()}
    cases = []
    for row,col,target in [(2,3,192),(2,4,203),(2,5,196),(2,6,215),(25,12,232)]:
        arms = {}
        for arm in states:
            records = []
            for frame in range(5985,5994):
                raw = states[arm][frame]
                if len(raw) != 196608:
                    raise ValueError('Wrong memory geometry')
                offset = row*64+col*2
                records.append(dict(frame=frame,source=raw[0x12000+row*32+col],
                    prepared=raw[0x3000+offset],vram=raw[0x24000+offset],
                    prepared_high=raw[0x3001+offset],vram_high=raw[0x24001+offset],
                    flags=raw[0x1d00+row]))
            arms[arm] = records
        cases.append(dict(row=row,column=col,target=target,records=arms,
                          attribution=attribute(arms['before'],arms['after'],target)))
    events = {}
    selected = {0xc087e4:'row-room entry',0xc083d7:'scalar row',
                0xc05000:'original-row DMA trigger',0xc05083:'alias-row DMA trigger',
                0xc0d2bc:'audio sender entry',0xc0d2f9:'audio sender return'}
    for arm,root in (('before',parent_trace),('after',trial_trace)):
        p=root/'service-instructions.json'; proof=bound_report(p)
        if not proof['observer_neutral'] or proof['first']>5989 or proof['last']<5990:
            raise ValueError('Missing neutral instruction coverage')
        sources.update(proof['sources']);sources[str(p)]=sha(p)
        events[arm]=[]
        with Path(proof['trace']).open() as stream:
            for r in csv.reader(stream):
                pc=int(r[4],16)
                if int(r[0]) in (5989,5990) and pc in selected:
                    events[arm].append(dict(frame=int(r[0]),line=int(r[1]),cycle=int(r[2]),
                        master_clock=int(r[3]),pc=r[4],event=selected[pc],a=int(r[6]),
                        x=int(r[7]),y=int(r[8])))
    rows={}
    for arm,root in (('before',parent_normal),('after',trial_normal)):
        receipt,rows[arm]=verify_capture(root)
        expected=('67fa19ee60b76af7c8e7ec581075eabb97efb19e7ce933e2cc34db66882cbda2'
                  if arm=='before' else 'cfa07c033f0cf7211f5f5b2c28d214f562c3f384518b6ad24aae5d1f43281912')
        if receipt['rom_sha256']!=expected:
            raise ValueError('Wrong cartridge')
        for name in ('capture.json','timeline.json'):
            p=root/name;sources[str(p)]=sha(p)
    if len(rows['before'])!=len(rows['after']):
        raise ValueError('Different timeline lengths')
    changed=[a['frame'] for a,b in zip(rows['before'],rows['after'])
             if a['video_sha256']!=b['video_sha256']]
    out.mkdir()
    body='''<!doctype html><meta charset="utf-8"><title>Receiver text deadline attribution</title>
<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}
a{color:cyan}pre{white-space:pre-wrap}.pair{display:flex;gap:10px}img{width:48%;image-rendering:pixelated}</style>
<h1>Receiver3934: source-phase change and a missed ready-row deadline</h1>
<p>Parent3890 left, trial3934 right. ALEX source appears two frames later in the trial;
its preparation lag is unchanged and publication lag is shorter. The dialogue letter
has identical source/preparation times but reaches VRAM one frame later. These are
separate failures, not five instances of the same cause. Full neutral memory and CPU
observations; frame-boundary memory is not physical scanout proof.</p>
<p>At frame5990 the trial transfers mirror89 at line252/cycle1130, then enters the
alias25 gate at line253/cycle850 without triggering its DMA. The parent transfers
visible25 at line247/cycle840 and mirror89 at line249/cycle156. Keep the beam safety
gate intact. Audio timing improvements do not qualify this regression for release.</p>
<p>All full-route changed pictures follow, including frame5979's unresolved logical-camera
sample. No alignment or selected-picture equivalence claim. No release verdict.</p>
<p><a href="report.json">Exact records and bindings</a> ·
<a href="../receiver-local-poll-audio-review-3942/">Native full-route audio</a></p>'''
    body+='<pre>'+html.escape(json.dumps([dict(row=c['row'],column=c['column'],**c['attribution'])
                                          for c in cases],indent=2))+'</pre>'
    for frame in changed:
        body+=f'<h2>Frame {frame}</h2><div class="pair">'
        for arm,root in (('before',parent_normal),('after',trial_normal)):
            row=rows[arm][frame-1];p=root/row['frame_image']
            if sha(p)!=row['frame_image_sha256']:
                raise ValueError('Changed picture')
            name=f'{arm}-{frame}.png';shutil.copyfile(p,out/name);sources[str(p)]=sha(p)
            body+=f'<img src="{name}" loading="lazy" alt="{arm} frame {frame}">'
        body+='</div>'
    (out/'index.html').write_text(body)
    if any(sha(Path(p))!=h for p,h in sources.items()):
        raise ValueError('Changed bound source')
    report=dict(cases=cases,events=events,changed_frames=changed,sources=sources,
                artifacts={p.name:sha(p) for p in out.iterdir()},release_ready=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(changed_pictures=len(changed),cases=[c['attribution'] for c in cases])))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ('before','after','parent_trace','trial_trace','parent_normal','trial_normal','out'):
        parser.add_argument('--'+k.replace('_','-'),type=Path,required=True)
    audit(**vars(parser.parse_args()))
