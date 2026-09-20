"""Bind the real line-wrap failure, corrected full route, DMA and renderer checks."""
import argparse
import csv
import html
import json
from pathlib import Path
import shutil
from tools.audit_main_display_latency import bound_report
from tools.audit_hud_final_budget import decode
from tools.benchmark_report import sha,verify_capture


def review(out):
    if out.exists():raise ValueError('Fresh output required')
    sources={}
    def bind(path):
        r=bound_report(path);sources.update(r['sources']);sources[str(path)]=sha(path);return r
    fault=bind(Path('build/postrow-fault-instructions-3779/fault-instructions.json'))
    dma=bind(Path('build/final-window-dma-audit-3790/report.json'))
    render=bind(Path('build/final-window-render-audit-3788/report.json'))
    render_proof=bind(Path('build/final-window-render-observed-3785/renderer-observer.json'))
    roots=dict(before=Path('build/postrow-stop-full-3775'),after=Path('build/final-window-full-3782'))
    receipts={};rows={}
    for k,root in roots.items():
        receipts[k],rows[k]=verify_capture(root)
        for name in ('capture.json','timeline.json','audio.wav'):sources[str(root/name)]=sha(root/name)
    rom=Path('build/final-window-game-3780/native-cpu.sfc')
    if (dma['rom_sha256']!=sha(rom) or render_proof['sources'].get(str(rom))!=sha(rom)
            or receipts['after']['rom_sha256']!=sha(rom)):
        raise ValueError('Mixed candidate evidence')
    if not fault['observer_neutral'] or fault['game_passed']:
        raise ValueError('Missing retained negative')
    old_faults=[r['frame'] for r in rows['before'] if r['fault']]
    new_faults=[r['frame'] for r in rows['after'] if r['fault']]
    differences={k:[a['frame'] for a,b in zip(rows['before'],rows['after']) if a[k]!=b[k]]
                 for k in ('probe_052b','input_requested','input_delivered','game_ram_hex','video_sha256')}
    if not old_faults or old_faults[0]!=6337 or new_faults or not dma['passed'] or not render['passed']:
        raise ValueError('Wrap recovery or broad guards failed')
    if len(rows['before'])!=len(rows['after']) or any(differences[k] for k in ('probe_052b','input_requested','input_delivered')):
        raise ValueError('Counter/input tradeoff')
    instructions=[]
    with Path(fault['trace']).open() as stream:
        for raw in csv.reader(stream):
            if int(raw[0]) in (6336,6337):
                r=decode(raw)
                if r['pc'] in (0xc086c8,0xc086cd,0xc086d0,0xc086dc,0xc086e2,0xc08460,0xc084f9,0xc085d1):
                    instructions.append(r)
    if not any(r['pc']==0xc086e2 and r['line']==0 for r in instructions):
        raise ValueError('Missing actual wrapped admission')
    report=dict(sources=sources,old_fault_frames=old_faults,new_fault_frames=new_faults,
                first_fault=6337,old_fault_is_sticky=True,negative_trace=instructions,
                differences=differences,frames=len(rows['after']),dma=dict(passed=dma['passed'],
                    transfers=dma['dma_transfers'],latest_visible_end=dma['latest_visible_end'],populations=dma['populations']),
                renderer={k:render[k] for k in ('passed','eligible_frames','checked_held_frames',
                    'coverage_failures','splits','stale_camera_failures')},release_ready=False,
                physical_verified=False,pop_free_verified=False,scope=__doc__+
                ' Counter/input equality is not full-RAM equality or matched original-NES combat speed. '
                'General DMA audit excludes HDMA; renderer checks street scanlines, not all tile contents.')
    out.mkdir(parents=True)
    body='<!doctype html><meta charset="utf-8"><title>Final VBlank window recovery3780</title><style>body{background:#091016;color:#eef;font:17px/1.6 system-ui;max-width:1100px;margin:32px auto}a{color:cyan}.pair{display:flex;gap:16px}figure{margin:0;flex:1}img{width:100%;image-rendering:pixelated}pre{white-space:pre-wrap}</style><h1>Shop-transition overrun fixed: reject wrapped scanline0</h1><p>Candidate3780, offline only. Require240≤latched line&lt;254 at the final palette/display gate. Same upper cutoff; no graphics assets changed.</p>'
    body+=f'<p>The failing3764 trace enters the check at261/1314, latches0 after wrap and incorrectly admits the final batch. The overrun first appears at6337 and remains latched for{len(old_faults)}frames—not{len(old_faults)}independent overruns. New3780 retains the transition until the following valid VBlank; no fault occurs in{len(rows["after"])}frames.</p>'
    body+='<pre>'+html.escape(json.dumps(dict(dma=report['dma'],renderer=report['renderer']),indent=2))+'</pre>'
    for f in (6336,6337,6338):
        body+=f'<h2>Frame{f}</h2><div class="pair">'
        for k,root in roots.items():
            r=rows[k][f-1];p=root/r['frame_image']
            if sha(p)!=r['frame_image_sha256']:raise ValueError('Changed selected frame')
            sources[str(p)]=sha(p);name=f'{k}-{f}.png';shutil.copyfile(p,out/name)
            body+=f'<figure><img src="{name}"><figcaption>{k}: transition{r["native"]["transition_state"]}, fault{r["fault"]}</figcaption></figure>'
        body+='</div>'
    body+='<p>All full-route differences remain in JSON. Counter and delivered inputs match, but full RAM/pictures do not. Menus, broader publication liveness, heavy-combat original speed, pop-free audio and physical SNES/EverDrive acceptance remain open.</p><p><a href="report.json">Bound trace, all differences and limits</a> · <a href="../final-window-audio-review-3789/">Current native audio and short-route visual changes</a> · <a href="../progress-3728/">Progress</a> · <a href="https://github.com/struktured-labs/river-city-ransom-snes/issues/18">Issue18</a></p>'
    (out/'index.html').write_text(body)
    sources[str(Path(__file__))]=sha(Path(__file__))
    report['artifacts']={p.name:sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(frames=report['frames'],dma=report['dma'],renderer=report['renderer'])))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    review(**vars(parser.parse_args()))
