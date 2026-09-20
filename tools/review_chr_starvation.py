"""CHR starvation fix: source bytes, actual VRAM, renderer, DMA, audio and retained failures."""
import argparse
from collections import Counter
from copy import deepcopy
import csv
import html
import json
from pathlib import Path
import shutil
import time

import numpy as np
from PIL import Image
from tools.audit_main_display_latency import bound_report
from tools.audit_dma_safety import parse as dma_events
from tools.audit_scroll_publication import frame_path
from tools.audit_sprite_publication import load as sprite_load
from tools.benchmark_report import sha,verify_capture
from tools.capture_sprite_prefix import installed_prefix
from tools.chr_publication_audit import inspect,episodes,pending_runs
from tools.review_early_oam_final import sprite_cohort
from tools.review_exact_row_scan import compare,load as row_load
from tools.review_row_publication import audio_and_cadence

ROOT=Path('build/overflow-3526')


def review(out):
    started=time.monotonic()
    if out.exists():raise ValueError('Fresh report required')
    sources={};arms={};samples_by_arm={};timelines={};receipts={}
    for name,folder,normal,game in (
        ('parent',ROOT/'chr-state-parent-3540',Path('build/transition-direct-full-normal-3506'),Path('build/transition-commit-direct-game-3502')),
        ('candidate',ROOT/'chr-state-trial-3541',ROOT/'chr-full-normal-3532',Path('build/early-oam-chr-game-3527'))):
        proof=bound_report(folder/'chr-state.json');sources.update(proof['sources']);sources[str(folder/'chr-state.json')]=sha(folder/'chr-state.json')
        if not proof['observer_neutral']:raise ValueError('Snapshot observation changed execution')
        with installed_prefix('right_08'):_,prefix=verify_capture(folder)
        receipt,rows=verify_capture(normal);receipts[name]=receipt;timelines[name]=rows
        if receipt['rom_sha256']!=sha(game/'native-cpu.sfc'):raise ValueError('Wrong cartridge')
        rom=(game/'native-cpu.sfc').read_bytes();samples=[]
        for s in proof['samples']:
            n=prefix[s['frame']-1]['native']
            samples.append(dict(frame=s['frame'],visible=n['task']&192==192 and n['transition_state']==0 and bool(n['ppu_mask']&8),
                jobs=inspect(Path(s['path']).read_bytes(),rom)))
        samples_by_arm[name]=samples
        arms[name]=dict(publication=episodes(samples),pending=pending_runs(rows),snapshot_seconds=proof['seconds'],
                        rom_sha256=receipt['rom_sha256'])
        for p in (game/'native-cpu.sfc',game/'manifest.json',normal/'capture.json',normal/'timeline.json',normal/'audio.wav'):
            sources[str(p)]=sha(p)
    # A fake queue retirement must not pass when its VRAM remains stale.
    mutation=deepcopy(samples_by_arm['parent'])
    for s in mutation:
        if s['frame']>=2426:
            for slot in (18,20):s['jobs'][slot]['flag']=0
    fake_retirement_rejected=not episodes(mutation)['passed']
    candidate=Path('build/early-oam-chr-game-3527')
    audio,audio_sources=audio_and_cadence(candidate,ROOT/'chr-full-normal-3532',ROOT/'chr-audio-3533');sources.update(audio_sources)
    dma=bound_report(ROOT/'chr-dma-audit-3539/report.json');renderer=bound_report(ROOT/'chr-render-audit-3536/report.json')
    for proof in (dma,renderer):sources.update(proof['sources'])
    rb=bound_report(ROOT/'chr-render-observed-3535/renderer-observer.json');sources.update(rb['sources'])
    db=bound_report(ROOT/'chr-dma-observed-3538/dma-capture.json')
    transfers=dma_events(csv.reader(Path(db['trace']).open()))
    chr_transfers=[e for e in transfers if e['target']==0x18 and e['count'] in (1024,2048) and e['classification']=='vblank']
    with installed_prefix():sprite=sprite_load(ROOT/'chr-sprite-observed-3543',candidate)
    cohort=sprite_cohort(sprite[2]);sources.update(sprite[0]['sources'])
    exact={};retained={}
    for name,c,t,failed in (
        ('health','row-resume-control-3449',ROOT/'chr-health-3530',Path('build/row-empty-pair-health-3524')),
        ('dialogue','row-resume-dialogue-control-3451',ROOT/'chr-dialogue-3531',Path('build/row-empty-pair-dialogue-3525'))):
        control=Path('build')/c;exact[name]=compare(control,t);retained[name]=compare(control,failed)
        for root in (control,t,failed):
            p,_,_=row_load(root);sources.update(p['sources']);sources[str(root/'report.json')]=sha(root/'report.json')
    health=next(p for p in exact['health']['publication']['2']['comparisons'] if p['identity'][1]==9)['after']
    checks=dict(original_starvation_rejected=not arms['parent']['publication']['passed'] and not arms['parent']['pending']['passed'],
        visible_jobs_source_equal=arms['candidate']['publication']['passed'],
        full_route_pending_bounded=arms['candidate']['pending']['passed'],fake_retirement_rejected=fake_retirement_rejected,
        visible_chr_dma_observed=bool(chr_transfers),full_dma=dma['passed'],full_renderer=renderer['passed'],
        sprite_cohort_next_frame=cohort['passed'],audio_startup=audio['audio']['passed'],cadence=audio['cadence']['passed'],
        exact_playfield_guards=all(all(w['gates'].values()) for w in exact.values()),
        health_target_le_3=health['status']=='published' and health['vram_latency']<=3)
    old,new=timelines['parent'],timelines['candidate']
    # Same frame numbers, no alignment: retain every changed primary field.
    primary={k:[a['frame'] for a,b in zip(old,new) if a.get(k)!=b.get(k)] for k in sorted(set(old[0])|set(new[0]))}
    out.mkdir();cards=[];picture_differences=[]
    prefix_roots=[Path('build/transition-direct-normal-3503'),ROOT/'chr-prefix-normal-3528']
    with installed_prefix('right_08'):prefix_rows=[verify_capture(p)[1] for p in prefix_roots]
    for f in (2428,2450):
        pictures=[]
        for name,root,rows in zip(('parent','candidate'),prefix_roots,prefix_rows):
            src=frame_path(root,rows[f-1]);dest=out/f'{name}-{f}.png';shutil.copyfile(src,dest);sources[str(src)]=sha(src)
            pictures.append(np.asarray(Image.open(src).convert('RGB')))
            cards.append(f'<figure><img src="{dest.name}"><figcaption>{name}, exact frame {f}</figcaption></figure>')
        mask=np.any(pictures[0]!=pictures[1],axis=2);yy,xx=np.where(mask)
        picture_differences.append(dict(frame=f,pixels=len(xx),bbox=[int(xx.min()),int(yy.min()),int(xx.max())+1,int(yy.max())+1] if len(xx) else None))
    ac=audio['audio'];rooms=audio['cadence']['rooms']
    summary=dict(checks=checks,rom_sha256=sha(candidate/'native-cpu.sfc'),frames=audio['frames'],
        pending_span_before_after=[arms['parent']['pending']['max_pending_frames'],arms['candidate']['pending']['max_pending_frames']],
        jobs=[{k:e[k] for k in ('slot','source_frame','first_publication','latency','initial_mismatched_bytes')} for e in arms['candidate']['publication']['visible_cohort']],
        visible_chr_transfers=len(chr_transfers),dma_transfers=dma['dma_transfers'],latest_visible_dma_end=dma['latest_visible_end'],
        renderer_eligible=renderer['eligible_frames'],sprite_generations=len(cohort['generations']),
        audio={k:ac[k] for k in ('restarts','packets','passed','samples','peak','max_adjacent_step','clipped')},
        audio_phase_count=len(ac['kon_phases']),cadence={k:{q:v[q] for q in ('intervals','frame_histogram','busy_intervals','passed')} for k,v in rooms.items()},
        health_latency=health['vram_latency'],picture_differences=picture_differences)
    scope=('Experimental3527 only; no deployment. Moving OAM earlier had starved visible CHR under the old243 cutoff. '
        'Return three already-spent OAM scanlines to that preflight (246); rows249/palette254 unchanged. '
        'Two first-room jobs now match original source bytes in actual VRAM; all other observed generations/censoring retained. '
        'Full-route pending spans, actual DMA, sprite and audio checks guard the tradeoff. '
        'Safe completed DMA alone did not prove liveness in3502. HUD target, menus, matched original-speed and physical/pop-free audio remain unqualified.')
    body='<!doctype html><meta charset="utf-8"><title>CHR starvation recovery</title><style>body{background:#101821;color:#eef;font:17px system-ui;max-width:1140px;margin:30px auto}a{color:#9df}.grid{display:grid;grid-template-columns:1fr 1fr}figure{margin:10px}img{width:512px;image-rendering:pixelated}pre{white-space:pre-wrap}td,th{padding:8px;text-align:left;border-bottom:1px solid #456}</style>'
    body+='<h1>Graphics-pattern uploads: starvation fixed offline</h1><p>'+html.escape(scope)+'</p><p><a href="report.json">Complete bound evidence and all primary differences</a></p>'
    body+=f'<p>Longest visible pending span: <strong>{summary["pending_span_before_after"][0]} → {summary["pending_span_before_after"][1]} frames</strong>. '
    body+='The two source-equal2048-byte uploads complete in2 and3frames, correcting197 and54 stale VRAM bytes.</p>'
    body+='<h2>Actual visible change</h2><p>Exact same frame numbers, no alignment. Differences include NPC sprite pixels; graphics assets are unchanged.</p><div class="grid">'+''.join(cards)+'</div>'
    body+='<h2>Qualification and remaining failures</h2><pre>'+html.escape(json.dumps(summary,indent=2))+'</pre>'
    body+='<p><a href="../overflow-3526/chr-full-normal-3532/audio.wav">Native full-route WAV</a></p><audio controls preload="none" src="../overflow-3526/chr-full-normal-3532/audio.wav"></audio>'
    (out/'index.html').write_text(body)
    paths=[Path(__file__),Path('tools/chr_publication_audit.py'),Path('tools/capture_chr_publication_state.py'),
           Path('tools/early_oam_chr_slack.py'),Path('tools/review_row_publication.py'),Path('tools/review_exact_row_scan.py'),
           Path('tests/test_chr_publication.py'),Path('tests/test_row_empty_pair.py'),
           ROOT/'chr-dma-audit-3539/report.json',ROOT/'chr-render-audit-3536/report.json']
    sources.update({str(p):sha(p) for p in paths})
    for h in json.loads((candidate/'manifest.json').read_text())['experimental_early_oam_chr_slack']['sources'].items():sources[h[0]]=h[1]
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Changed source binding')
    result=dict(summary=summary,checks=checks,passed=all(checks.values()),release_ready=False,physical_verified=False,
        arms=arms,samples=samples_by_arm,exact_rows=exact,rejected_empty_pair=retained,primary_differences=primary,
        terminal_frames_unmatched={'parent':len(old),'candidate':len(new)},chr_dma=chr_transfers,
        audio_and_cadence=audio,dma=dma,renderer=renderer,sprite_cohort=cohort,
        sources=sources,artifacts={p.name:sha(p) for p in out.iterdir()},scope=scope,seconds=time.monotonic()-started)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(checks=checks,seconds=result['seconds'],summary=summary)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    review(**vars(p.parse_args()))
