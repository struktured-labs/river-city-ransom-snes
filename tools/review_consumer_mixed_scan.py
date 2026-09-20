"""Audit mixed-group scanning against actual pictures, boot, queues, DMA and native audio."""
import argparse
import csv
import html
import json
from pathlib import Path
import shutil
import time
import numpy as np
from PIL import Image
from tools.audit_main_display_latency import bound_report
from tools.audit_restored_clock import decode,reconstruct
from tools.audit_sprite_publication import load as sprite_load
from tools.benchmark_report import sha,verify_capture
from tools.capture_sprite_prefix import installed_prefix
from tools.chr_publication_audit import inspect,episodes,pending_runs
from tools.review_early_oam_final import sprite_cohort
from tools.review_exact_row_scan import compare,load as row_load
from tools.review_row_publication import audio_and_cadence

ROOT=Path('build/overflow-3526')
GAME=Path('build/consumer-mixed-game-3583')


def review(out):
    started=time.monotonic()
    if out.exists():raise ValueError('Fresh report required')
    sources={}
    def proof(path):
        r=bound_report(path);sources.update(r['sources']);sources[str(path)]=sha(path);return r
    variants={}
    controls=[Path('build/row-resume-control-3449'),Path('build/row-resume-dialogue-control-3451')]
    pairs={
        'parent3527':('chr-health-3530','chr-dialogue-3531'),
        'row250':('row-slack250-health-3549','row-slack250-dialogue-3550'),
        'row251':('row-slack251-health-3552','row-slack251-dialogue-3553'),
        'producer3556':('producer-group-health-3557','producer-group-dialogue-3558'),
        'invalid_entry3559':('consumer-linear-health-3560','consumer-linear-dialogue-3561'),
        'invalid_entry3569':('consumer-aligned-health-3571','consumer-aligned-dialogue-3572'),
        'invalid_entry3573':('consumer-word-health-3574','consumer-word-dialogue-3575'),
        'word3579':('consumer-word-fixed-health-3580','consumer-word-fixed-dialogue-3581'),
        'mixed3583':('consumer-mixed-health-3584','consumer-mixed-dialogue-3585')}
    summaries=[]
    for name,folders in pairs.items():
        windows={}
        for w,c,f in zip(('health','dialogue'),controls,folders):
            root=ROOT/f;windows[w]=compare(c,root)
            for p in (c,root):
                r,_,_=row_load(p);sources.update(r['sources']);sources[str(p/'report.json')]=sha(p/'report.json')
        h=next(p['after'] for p in windows['health']['publication']['2']['comparisons'] if p['identity'][1]==9)
        d=[p['after'] for p in windows['dialogue']['publication']['25']['comparisons']]
        windows['health_target']=h['status']=='published' and h['vram_latency']<=3
        windows['dialogue_bounded']=len(d)==11 and all(p['status']=='published' and p['vram_latency']<=3 for p in d)
        variants[name]=windows
        summaries.append(dict(variant=name,health=h['vram_latency'],dialogue=[e['vram_latency'] for e in d],
            invalid_instruction_entry=name.startswith('invalid'),
            narrow_gameplay_guards=all(all(windows[w]['gates'].values()) for w in ('health','dialogue'))))
    boot={}
    for name,folder in [('invalid_entry3559','consumer-linear-boot-normal-3564'),
                        ('invalid_entry3569','consumer-aligned-boot-normal-3570'),
                        ('word3579','consumer-word-fixed-boot-normal-3582'),
                        ('mixed3583','consumer-mixed-boot-normal-3586')]:
        root=ROOT/folder
        with installed_prefix('right_08'):receipt,rows=verify_capture(root)
        boot[name]=dict(complete=receipt['capture_complete'],frames=receipt['frames'],
            last_phase=rows[-1]['phase'],last_native=rows[-1]['native'])
        for p in (root/'capture.json',root/'timeline.json',root/'audio.wav'):sources[str(p)]=sha(p)
    normal=ROOT/'consumer-mixed-full-normal-3587'
    receipt,timeline=verify_capture(normal)
    if receipt['rom_sha256']!=sha(GAME/'native-cpu.sfc'):raise ValueError('Wrong full-route cartridge')
    audio,bindings=audio_and_cadence(GAME,normal,ROOT/'consumer-mixed-audio-3588');sources.update(bindings)
    dma=proof(ROOT/'consumer-mixed-dma-audit-3591/report.json')
    renderer=proof(ROOT/'consumer-mixed-render-audit-3594/report.json')
    proof(ROOT/'consumer-mixed-render-observed-3593/renderer-observer.json')
    with installed_prefix():sp=sprite_load(ROOT/'consumer-mixed-sprite-observed-3596',GAME)
    sources.update(sp[0]['sources']);cohort=sprite_cohort(sp[2])
    chr_root=ROOT/'consumer-mixed-chr-state-3597';chr_proof=proof(chr_root/'chr-state.json')
    if not chr_proof['observer_neutral']:raise ValueError('Non-neutral CHR observation')
    with installed_prefix('right_08'):_,chr_timeline=verify_capture(chr_root)
    rom=(GAME/'native-cpu.sfc').read_bytes();chr_samples=[]
    for s in chr_proof['samples']:
        n=chr_timeline[s['frame']-1]['native']
        chr_samples.append(dict(frame=s['frame'],visible=n['task']&192==192 and n['transition_state']==0 and bool(n['ppu_mask']&8),
            jobs=inspect(Path(s['path']).read_bytes(),rom)))
    chr_jobs=episodes(chr_samples);pending=pending_runs(timeline)
    clocks={}
    for name,folder,game in [('parent','row-instructions-on-3555',Path('build/early-oam-chr-game-3527')),
                           ('mixed','consumer-mixed-clock-on-3599',GAME)]:
        root=ROOT/folder;r=proof(root/'report.json')
        if not r['passed'] or not r['observer_neutral']:raise ValueError('Non-neutral clock')
        for p,h in r['artifacts'].items():
            if sha(root/p)!=h:raise ValueError('Changed clock artifact')
        rows=[decode(x) for x in csv.reader((root/'instructions.csv').open())]
        clocks[name]=reconstruct(rows,r['first'],r['last'],(game/'native-cpu.sfc').read_bytes())
        ins=[x for x in rows if x['kind']=='I']
        clocks[name]['wrong_scalar_operand_entries']=sum(x['pc']==0xc083d9 for x in ins)
        clocks[name]['correct_scalar_loads']=sum(x['pc']==0xc083d7 and x['opcode']==0xbd for x in ins)
        clocks[name]['row_room']=[{k:x[k] for k in ('frame','line','cycle','clock','x','y')} for x in ins if x['pc']==0xc087e4]
        del rows,ins
    exact=variants['mixed3583']
    h=next(p['after'] for p in exact['health']['publication']['2']['comparisons'] if p['identity'][1]==9)
    _,pictures,_=row_load(ROOT/'consumer-mixed-health-3584')
    pixel=[]
    for frame in (h['source_frame'],h['vram_frame']-1,h['vram_frame']):
        row=next(x for x in pictures if x['frame']==frame)
        pixel.append(np.asarray(Image.open(ROOT/'consumer-mixed-health-3584'/row['frame_image']).convert('RGB'))[16:24,72:80])
    picture_edge=not np.array_equal(pixel[-1],pixel[0]) and not np.array_equal(pixel[-1],pixel[-2])
    checks=dict(health_target=exact['health_target'],actual_health_picture_edge=picture_edge,
        dialogue_bounded=exact['dialogue_bounded'],narrow_gameplay_guards=all(all(exact[w]['gates'].values()) for w in ('health','dialogue')),
        fresh_boot=boot['mixed3583']['complete'],full_route=receipt['capture_complete'],dma=dma['passed'],renderer=renderer['passed'],
        sprite_next_frame=cohort['passed'],chr_source_equal=chr_jobs['passed'],chr_pending_bounded=pending['passed'],
        audio_startup=audio['audio']['passed'],cadence=audio['cadence']['passed'],
        clock_instructions=all(c['wrong_scalar_operand_entries']==0 and c['correct_scalar_loads']>0 for c in clocks.values()),
        broken_boot_rejected=not boot['invalid_entry3559']['complete'] and not boot['word3579']['complete'],
        censored_dialogue_rejected=not variants['invalid_entry3573']['dialogue_bounded'],
        previous_health_delay_rejected=not variants['parent3527']['health_target'])
    out.mkdir();cards=[]
    for frame in (8244,8245):
        for label,folder in [('parent3527','chr-health-3530'),('mixed3583','consumer-mixed-health-3584')]:
            root=ROOT/folder;_,rows,_=row_load(root);row=next(x for x in rows if x['frame']==frame)
            src=root/row['frame_image'];dest=out/f'{label}-{frame}.png';shutil.copyfile(src,dest);sources[str(src)]=sha(src)
            cards.append(f'<figure><img src="{dest.name}"><figcaption>{label}: exact frame {frame}</figcaption></figure>')
    shutil.copyfile(normal/'audio.wav',out/'native-audio.wav')
    if sha(out/'native-audio.wav')!=sha(normal/'audio.wav'):raise ValueError('Changed published PCM')
    summary=dict(checks=checks,rom_sha256=sha(GAME/'native-cpu.sfc'),health_before_after=[5,h['vram_latency']],
        dialogue=[p['after']['vram_latency'] for p in exact['dialogue']['publication']['25']['comparisons']],
        boot_frames=boot['mixed3583']['frames'],full_frames=receipt['frames'],dma_transfers=dma['dma_transfers'],
        latest_visible_dma_end=dma['latest_visible_end'],renderer_eligible=renderer['eligible_frames'],
        sprite_generations=len(cohort['generations']),chr_jobs=chr_jobs['visible_cohort'],max_chr_pending=pending['max_pending_frames'],
        audio={k:audio['audio'][k] for k in ('passed','packets','restarts','samples','peak','max_adjacent_step','clipped')},
        audio_phases=len(audio['audio']['kon_phases']),
        cadence={k:{q:v[q] for q in ('intervals','frame_histogram','busy_intervals','passed')} for k,v in audio['cadence']['rooms'].items()})
    scope=('Experimental3583, offline only. Mixed-group consumer search avoids repeatedly reading the same flags; '
        'no new queue priority, graphics, sound engine, or DMA deadlines. Health source8242 reaches VRAM and picture8245 '
        'instead of8247. Exact playfield/sprite/counter/camera/input guards hold, but full cross-ROM state/PCM differ. '
        'Dialogue retains the2–3frame envelope, not identical per-glyph timing. Original-NES matched speed, menus, '
        'both-direction full traversal, physical capture and acoustic/pop-free acceptance remain open. No deployment.')
    body='<!doctype html><meta charset="utf-8"><title>Row publication: mixed-group scan</title><style>body{background:#101821;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}a{color:#9df}.grid{display:grid;grid-template-columns:1fr 1fr}figure{margin:10px}img{width:100%;image-rendering:pixelated}pre{white-space:pre-wrap}</style>'
    body+='<h1>HUD publication: five frames → three</h1><p>'+html.escape(scope)+'</p>'
    body+='<p>Exact-frame screenshots: top HUD changes in3583 at8245; the playfield remains pixel-identical in this replay.</p><div class="grid">'+''.join(cards)+'</div>'
    body+='<h2>Qualification—not a release verdict</h2><pre>'+html.escape(json.dumps(summary,indent=2))+'</pre>'
    body+='<h2>Native full-route audio</h2><p>Unmodified32040Hz stereo PCM. Quantitative startup checks are not proof of pop-free sound; no subjective hearing claim.</p><audio controls preload="none" src="native-audio.wav"></audio>'
    body+='<h2>Retained failures</h2><p>Deadline250/251 and producer grouping did not improve the symptom. '
    body+='3559/3569/3573 used a wrong scalar continuation inside an operand; their apparent gains are invalid. '
    body+='3579 corrected that integration bug but still failed fresh boot. The real bad helper now fails a real-ROM continuation test. '
    body+='Only3583 completes the listed checks. No failed/censored event was removed.</p><p><a href="report.json">All generation chains, primary differences, retained failures and source bindings</a></p>'
    (out/'index.html').write_text(body)
    paths=[Path(__file__),GAME/'manifest.json',GAME/'native-cpu.sfc',normal/'capture.json',normal/'timeline.json',normal/'audio.wav']
    paths += [Path('tests')/f for f in ('test_producer_group_scan.py','test_consumer_linear_scan.py','test_consumer_aligned_scan.py',
        'test_consumer_word_scan.py','test_consumer_word_entry_fix.py','test_consumer_mixed_scan.py')]
    paths += [Path('tools')/f for f in ('consumer_mixed_scan.py','review_exact_row_scan.py','review_row_publication.py',
        'chr_publication_audit.py','audit_restored_clock.py','review_early_oam_final.py')]
    sources.update({str(p):sha(p) for p in paths})
    sources.update(json.loads((GAME/'manifest.json').read_text())['experimental_consumer_linear_scan']['sources'])
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Changed audit source')
    result=dict(summary=summary,checks=checks,passed=all(checks.values()),release_ready=False,physical_verified=False,
        variants=variants,boot=boot,clock=clocks,dma=dma,renderer=renderer,sprite_cohort=cohort,
        chr_samples=chr_samples,chr_jobs=chr_jobs,pending=pending,audio_and_cadence=audio,
        sources=sources,artifacts={p.name:sha(p) for p in out.iterdir()},scope=scope,seconds=time.monotonic()-started)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(summary=summary,seconds=result['seconds'],sources=len(sources))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    review(**vars(p.parse_args()))
