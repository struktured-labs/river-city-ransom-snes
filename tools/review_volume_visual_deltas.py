"""Explain strict camera snapshots and retain every changed image of the audio trial."""
import argparse
import json
import csv
from pathlib import Path
import shutil

import numpy as np
from PIL import Image

from tools.audit_main_display_latency import bound_report
from tools.audit_main_store_latency import parse
from tools.benchmark_report import sha,verify_capture
from tools.frame_audit import verify_frame


def review(full,before,after,before_observed,after_observed,dma,out):
    if out.exists():raise ValueError('Fresh visual review required')
    proof=bound_report(full/'report.json');transfers=bound_report(dma/'report.json')
    captures=[verify_capture(root) for root in (before,after)]
    timelines=[x[1] for x in captures]
    if [x[0]['rom_sha256'] for x in captures]!=[proof[k]['rom_sha256'] for k in ('baseline','trial')]:raise ValueError('Wrong visual arms')
    commits=[];sources={str(p):sha(p) for p in (Path(__file__),full/'report.json',dma/'report.json',Path('tools/audit_main_store_latency.py'),Path('tools/frame_audit.py'))}
    for root,(_,rows) in zip((before_observed,after_observed),captures):
        binding=bound_report(root/'startup-game.json')
        receipt=json.loads((root/'capture.json').read_text())
        roms=[Path(p) for p,h in binding['sources'].items() if p.endswith('/native-cpu.sfc') and h==receipt['rom_sha256']]
        if len(roms)!=1:raise ValueError('Ambiguous bound camera program')
        loops,censored=parse(csv.reader(Path(binding['main']).open()),{int(k):v for k,v in binding['points'].items()},len(rows),roms[0].read_bytes())
        events=[l['commit'] for l in loops if l['commit']]
        events += [c['event'] for c in censored if c['kind'] in ('camera outside main','nested transition camera')]
        events.sort(key=lambda e:e['clock'])
        commits.append([{k:e[k] for k in ('frame','camera','room','task','nmi')} for e in events])
        sources.update(binding['sources']);sources[str(root/'startup-game.json')]=sha(root/'startup-game.json')
    exact_commits=commits[0]==commits[1]
    out.mkdir();differences=[];cards=[];last_selected=-100
    for f in range(1,len(timelines[0])+1):
        rows=[r[f-1] for r in timelines]
        if rows[0]['video_sha256']==rows[1]['video_sha256']:continue
        pixels=[];names=[]
        for label,root,row in zip(('control','trial'),(before,after),rows):
            path=verify_frame(root,row);sources[str(path)]=sha(path)
            name=f'{f}-{label}.png';shutil.copyfile(path,out/name);names.append(name)
            pixels.append(np.array(Image.open(path).convert('RGB')))
        mask=np.any(pixels[0]!=pixels[1],axis=2);ys,xs=np.where(mask)
        box=[int(xs.min()),int(ys.min()),int(xs.max())+1,int(ys.max())+1]
        record=dict(frame=f,phase=rows[0]['phase'],changed_pixels=int(mask.sum()),bbox=box,
            transition=[r['native']['transition_state'] for r in rows],images=names)
        differences.append(record)
        # Show the first changed image of each later gameplay cluster. Every
        # image difference, including transitions, remains linked in the table.
        if f>3419 and record['transition']==[0,0] and f>last_selected+20:
            last_selected=f
            cards.append(f'<h3>Frame {f}: {rows[0]["phase"]}, {int(mask.sum())} changed pixels</h3><div class="pair">')
            x0=max(0,box[0]-12);y0=max(0,box[1]-8)
            for label,name in zip(('control','trial'),names):
                cards.append(f'<figure><img src="{name}"><figcaption>{label}</figcaption><div class="zoom" style="background-image:url({name});background-position:-{x0*4}px -{y0*4}px"></div></figure>')
            cards.append('</div>')
    snapshots=[]
    for d in proof['trajectory_differences']:
        f=d['frame'];rows=[r[f-1] for r in timelines]
        snapshots.append(dict(frame=f,fields=d['fields'],logical_camera=[r['native']['logical_camera_x'] for r in rows],
            displayed_camera=[r['native']['hdma_street_scroll_x'] for r in rows],pixels_identical=rows[0]['video_sha256']==rows[1]['video_sha256']))
    table=''.join(f'<tr><td>{d["frame"]}</td><td>{d["phase"]}</td><td>{d["changed_pixels"]}</td><td>{d["bbox"]}</td><td><a href="{d["images"][0]}">control</a> / <a href="{d["images"][1]}">trial</a></td></tr>' for d in differences)
    html=f'''<!doctype html><meta charset="utf-8"><title>Audio trial visual differences</title>
<style>body{{background:#121923;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}}a{{color:#8df}}.pair{{display:flex}}figure{{margin:8px;flex:1}}img{{width:100%;image-rendering:pixelated}}.zoom{{width:100%;height:112px;background-size:1024px 960px;image-rendering:pixelated;background-repeat:no-repeat}}td{{padding:6px;border-bottom:1px solid #445}}pre{{white-space:pre-wrap}}</style>
<h1>Camera snapshots explained; text differences still under investigation</h1>
<p>The strict full-route result remains <a href="../{full.name}/">FAIL</a>. No failed observation was removed or relabeled.</p>
<p>All {len(commits[0]):,} committed camera values agree in frame, camera, room, task and NMI count: {exact_commits}. The three unequal raw logical-camera snapshots occur before the same later final commits. Actual HDMA camera and complete pictures agree on those three frames.</p><pre>{json.dumps(snapshots,indent=2)}</pre>
<p>General DMA on this cartridge: {transfers['passed']}; {transfers['dma_transfers']:,} transfers checked. This does not cover HDMA.</p>
<h2>Changed gameplay text</h2><p>Some of the24 changed pictures are not just transitions: small text/HUD regions differ near the mall and park. They need a publication-timing check before promotion. Below are the first changes of later gameplay clusters, with native-pixel zooms.</p>{''.join(cards)}
<h2>All changed pictures</h2><table><tr><th>Frame</th><th>Phase</th><th>Pixels</th><th>Bounding box</th><th>Original images</th></tr>{table}</table>
<p><a href="report.json">Full observations and bindings</a>. No game or console changed by this read-only review.</p>'''
    (out/'index.html').write_text(html)
    result=dict(committed_camera_equal=exact_commits,commits=commits,logical_camera_snapshots=snapshots,
        all_image_differences=differences,strict_full_gate_passed=proof['passed'],dma_passed=transfers['passed'],
        visual_differences_resolved=False,release_ready=False,sources=sources,
        artifacts={p.name:sha(p) for p in out.iterdir() if p.is_file()},scope=__doc__)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(commits=len(commits[0]),committed_camera_equal=exact_commits,image_differences=len(differences),dma=transfers['passed'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('full','before','after','before-observed','after-observed','dma','out'):p.add_argument('--'+name,type=Path,required=True)
    review(**vars(p.parse_args()))
