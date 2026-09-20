"""Audit transition/display consistency, retaining unchanged fade duration and rejected variants."""
import argparse
from collections import Counter
from copy import deepcopy
import html
import json
from pathlib import Path
import shutil
import time

from PIL import Image
from tools.audit_main_display_latency import bound_report
from tools.audit_renderer_failures import diagnose
from tools.audit_scroll_publication import frame_path
from tools.audit_sprite_publication import load as load_sprites
from tools.benchmark_report import sha, verify_capture
from tools.capture_sprite_prefix import installed_prefix
from tools.review_early_oam_final import sprite_cohort
from tools.review_row_publication import audio_and_cadence


def room_entry(root,rows):
    start=next(r['frame'] for r in rows if r['phase'].startswith('right_') and bytes.fromhex(r['game_ram_hex'])[0x42]==1)
    # Inspect ALL first60 entry frames, regardless of transition eligibility or fade.
    window=rows[start-1:start+59]
    if len(window)!=60:raise ValueError('Incomplete transition observation')
    frames=[]
    for r in window:
        black=Image.open(frame_path(root,r)).convert('RGB').getbbox() is None
        frames.append(dict(frame=r['frame'],black=black,transition=r['native']['transition_state'],
                           palette_fade=bytes.fromhex(r['game_ram_hex'])[0x692]))
    black=[f['frame'] for f in frames if f['black']]
    if not black:raise ValueError('Expected normal room fade absent')
    visible=next((f['frame'] for f in frames if f['frame']>black[0] and not f['black']),None)
    if visible is None:raise ValueError('Room never became visible')
    return dict(room_entry_frame=start,frames=frames,black_frames=black,black_count=len(black),
                first_visible_frame=visible,room_entry_to_visible=visible-start,
                first_visible_sha256=rows[visible-1]['video_sha256'])


def review(out):
    started=time.monotonic()
    if out.exists():raise ValueError('Fresh output required')
    sources={};arms={};timelines={};reports={}
    for name,normal,observed,audit in (
        ('parent','transition-parent-normal-3494','transition-parent-observed-3495','transition-parent-audit-3501'),
        ('candidate','transition-direct-normal-3503','transition-direct-observed-3504','transition-direct-audit-3505')):
        root=Path('build')/normal;obs=Path('build')/observed
        for capture in (root,obs):
            p=capture/'transition-prefix.json';proof=bound_report(p)
            sources.update(proof['sources']);sources[str(p)]=sha(p)
        if not proof['observer_neutral']:raise ValueError('Missing same-core neutral prefix')
        with installed_prefix('right_08'):
            receipt,rows=verify_capture(root);seen,other=verify_capture(obs)
        if rows!=other or receipt['core_sha256']!=seen['core_sha256'] or receipt['audio_sha256']!=seen['audio_sha256']:
            raise ValueError('Changed primary observation')
        p=Path('build')/audit/'report.json';r=bound_report(p);sources.update(r['sources']);sources[str(p)]=sha(p)
        reports[name]=r;timelines[name]=rows
        arms[name]=dict(rom_sha256=receipt['rom_sha256'],prefix_frames=len(rows),renderer=r,
                        entry=room_entry(root,rows),normal=str(root),observed=str(obs))
    before=arms['parent']['entry'];after=arms['candidate']['entry']
    # These are diagnostic event-relative durations, not aligned primary equality.
    no_fade_regression=(after['black_count']<=before['black_count'] and
                        after['room_entry_to_visible']<=before['room_entry_to_visible'])
    old,new=timelines['parent'],timelines['candidate']
    differences={k:[a['frame'] for a,b in zip(old,new) if a.get(k)!=b.get(k)] for k in sorted(set(old[0])|set(new[0]))}
    rejected={}
    for label,name in (('rollback_cutoff254','transition-trial-normal-3496'),('rollback_cutoff255','transition-slack-normal-3499')):
        root=Path('build')/name
        with installed_prefix('right_08'):receipt,rows=verify_capture(root)
        rejected[label]=dict(complete=receipt['capture_complete'],frames=len(rows),last_phase=rows[-1]['phase'],
            faults=[dict(frame=r['frame'],fault=r['fault'],registers=r['fault_registers']) for r in rows if r['fault']],
            rom_sha256=receipt['rom_sha256'],reason='Boot stalls at settings' if not receipt['capture_complete'] else 'VBlank overrun')
        if receipt['capture_complete'] and not rejected[label]['faults']:raise ValueError('Rejected variant no longer fails')
        for p in (root/'capture.json',root/'timeline.json',root/'audio.wav'):sources[str(p)]=sha(p)
    candidate=Path('build/transition-commit-direct-game-3502')
    with installed_prefix():sprite=load_sprites(Path('build/transition-direct-sprite-observed-3513'),candidate)
    cohort=sprite_cohort(sprite[2]);sources.update(sprite[0]['sources'])
    mutant=deepcopy(sprite[2]);g=next(g for g in mutant['generations'] if not g['left_censored'] and g['source_frame']<=2020)
    g['first_render']=None;g['source_to_first_render_frames']=None
    rejected_missing=not sprite_cohort(mutant)['passed']
    normal=Path('build/transition-direct-full-normal-3506');observed=Path('build/transition-direct-audio-3507')
    audio,bindings=audio_and_cadence(candidate,normal,observed);sources.update(bindings)
    full={}
    for name,path in (('dma','transition-direct-dma-audit-3516'),('renderer','transition-direct-render-audit-3510')):
        p=Path('build')/path/'report.json';proof=bound_report(p)
        sources.update(proof['sources']);sources[str(p)]=sha(p);full[name]=proof
    proof=bound_report(Path('build/transition-direct-render-observed-3509/renderer-observer.json'));sources.update(proof['sources'])
    m=json.loads((candidate/'manifest.json').read_text())
    for k in ('experimental_transition_display_commit','experimental_full_row_scan'):
        for p,h in m[k]['sources'].items():
            if sha(Path(p))!=h:raise ValueError('Changed patch source '+p)
            sources[p]=h
    checks=dict(prefix_missing_coverage_removed=bool(reports['parent']['coverage_failures']) and reports['candidate']['passed'],
        fade_not_extended=no_fade_regression,first_visible_picture_preserved=before['first_visible_sha256']==after['first_visible_sha256'],
        failed_variants_retained=True,sprite_cohort_next_frame=cohort['passed'],missing_sprite_mutation_rejected=rejected_missing,
        full_renderer=full['renderer']['passed'],full_dma=full['dma']['passed'],
        audio_startup=audio['audio']['passed'],cadence=audio['cadence']['passed'])
    # Missing renderer coverage must fail independently of a favorable report flag.
    sample=timelines['candidate'][-2:]
    mutation=diagnose(sample,[])
    checks['missing_renderer_mutation_rejected']=not mutation['passed'] and bool(mutation['coverage_failures'])
    out.mkdir();cards=[]
    for name in ('parent','candidate'):
        entry=arms[name]['entry'];root=Path(arms[name]['normal']);rows=timelines[name]
        for label,frame in (('last-black',entry['first_visible_frame']-1),('first-visible',entry['first_visible_frame'])):
            src=frame_path(root,rows[frame-1]);dest=out/f'{name}-{label}.png';shutil.copyfile(src,dest)
            sources[str(src)]=sha(src)
            cards.append(f'<figure><img src="{dest.name}"><figcaption>{name}: {label}, frame {frame}</figcaption></figure>')
    a=audio['audio'];c=audio['cadence']
    summary=dict(checks=checks,rom_sha256=m['rom_sha256'],full_frames=audio['frames'],
        black_frames_before_after=[before['black_count'],after['black_count']],
        room_entry_to_picture_before_after=[before['room_entry_to_visible'],after['room_entry_to_visible']],
        full_renderer={k:full['renderer'][k] for k in ('eligible_frames','coverage_failures','splits','stale_camera_failures')},
        dma={k:full['dma'][k] for k in ('dma_transfers','latest_visible_end','populations')},
        sprite_generations=len(cohort['generations']),
        audio={k:a[k] for k in ('restarts','packets','passed','samples','peak','max_adjacent_step','clipped')},
        audio_phase_count=len(a['kon_phases']),cadence={k:v for k,v in c.items() if not isinstance(v,list)})
    scope=('Offline experimental candidate only. Atomic transition/display admission plus equivalent direct-page readiness scan; '
        'cutoff remains254. The normal black fade is NOT shortened. Prefix boots one frame later; '
        'cross-ROM primary differences are retained without alignment. Full scans do not certify all tile content, '
        'original-NES speed, subjective pop-free audio, menus, physical hardware or the remaining health-tile latency. '
        'No ROM deployment. Two failed intermediate builds remain available.')
    text='<!doctype html><meta charset="utf-8"><title>Transition display commit</title><style>body{background:#101821;color:#eef;font:17px system-ui;max-width:1150px;margin:30px auto}a{color:#9df}pre{white-space:pre-wrap}.grid{display:flex;flex-wrap:wrap}figure{margin:12px}img{width:384px;image-rendering:pixelated}</style>'
    text+='<h1>Transition display commit: offline evidence</h1><p>'+html.escape(scope)+'</p><p><a href="report.json">All checks, rejected variants and primary differences</a></p>'
    text+='<pre>'+html.escape(json.dumps(summary,indent=2))+'</pre><h2>Original fade and first visible picture</h2><div class="grid">'+''.join(cards)+'</div>'
    text+='<p>Native, unnormalized full-route audio: <a href="../transition-direct-full-normal-3506/audio.wav">WAV</a></p><audio controls preload="none" src="../transition-direct-full-normal-3506/audio.wav"></audio>'
    (out/'index.html').write_text(text)
    for p in (Path(__file__),Path('tools/build_transition_display_commit.py'),Path('tools/build_transition_commit_direct.py'),
              Path('tools/capture_transition_prefix.py'),Path('tools/review_early_oam_final.py'),Path('tools/review_row_publication.py'),
              Path('tools/audit_renderer_failures.py'),candidate/'manifest.json',candidate/'native-cpu.sfc',
              Path('tests/test_transition_display_commit.py'),Path('tests/test_transition_commit_direct.py')):
        sources[str(p)]=sha(p)
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Changed evidence binding')
    result=dict(summary=summary,checks=checks,passed=all(checks.values()),release_ready=False,physical_verified=False,
        prefix=arms,primary_differing_frames_by_field=differences,
        unmatched_terminal_frames=[r['frame'] for r in new[len(old):]],rejected_variants=rejected,
        sprite_cohort=cohort,audio_and_cadence=audio,full=full,sources=sources,
        artifacts={p.name:sha(p) for p in out.iterdir()},scope=scope,seconds=time.monotonic()-started)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(checks=checks,seconds=result['seconds'],summary=summary)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    review(**vars(p.parse_args()))
