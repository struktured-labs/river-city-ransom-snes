"""Diagnose the retained blank-screen failure and qualify corrected early-sprite timing."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
import time

from tools.audit_main_display_latency import bound_report
from tools.audit_sprite_publication import load as sprites
from tools.benchmark_report import sha, verify_capture
from tools.capture_sprite_prefix import installed_prefix
from tools.review_exact_row_scan import compare
from tools.review_row_publication import audio_and_cadence


def blocks(raw):
    header=b'#!s9xsnp:0012\n'
    if not raw.startswith(header): raise ValueError('Need pinned version12 snapshot')
    pos=len(header); result={}
    while pos<len(raw) and raw[pos:pos+1]!=b'\0':
        h=raw[pos:pos+11]
        if len(h)!=11 or h[3:4]!=b':' or h[10:11]!=b':' or not h[4:10].isdigit():
            raise ValueError('Unsupported/truncated block header')
        key=h[:3].decode('ascii'); count=int(h[4:10]); pos+=11
        if key in result or pos+count>len(raw):raise ValueError('Duplicate/truncated block')
        result[key]=raw[pos:pos+count];pos+=count
    if any(raw[pos:]):raise ValueError('Unexpected snapshot suffix')
    for k,n in (('FIL',32768),('VRA',65536),('RAM',131072)):
        if len(result.get(k,b''))!=n:raise ValueError('Incomplete snapshot '+k)
    if len(result.get('PPU',b''))<576:raise ValueError('Truncated PPU')
    return result


def sprite_cohort(data, end=2020):
    if data['first']!=1978 or data['last']<end+4 or not data['structural_passed']:
        raise ValueError('Missing complete source window and follow-through')
    cohort=[g for g in data['generations'] if not g['left_censored'] and g['source_frame']<=end]
    return dict(source_window=[1978,end],observed_through=data['last'],generations=cohort,
        passed=bool(cohort) and all(g['first_render'] is not None and g['source_to_first_render_frames']==1 for g in cohort),
        after_source_window=[g for g in data['generations'] if g['source_frame']>end],
        scope='Fixed original source cohort through2020, with four more observed display frames. '
        'All later sources retained, including final right-censored source. No unrendered target source is dropped.')


def review(out):
    started=time.monotonic()
    if out.exists():raise ValueError('Fresh report required')
    candidate=Path('build/early-oam-final-game-3479');normal=Path('build/early-oam-final-normal-3484')
    dma=Path('build/early-final-dma-audit-3487');renderer=Path('build/early-final-render-audit-3491')
    control_state=Path('build/parent-boot-states-3478');bad_state=Path('build/early-oam-boot-states-3477')
    sources={}
    for root in (control_state,bad_state):
        proof=bound_report(root/'checkpoint-report.json')
        if not proof['full_timeline_equal'] or not proof['full_pcm_equal']:raise ValueError('Save observation changed execution')
        sources.update(proof['sources']);sources[str(root/'checkpoint-report.json')]=sha(root/'checkpoint-report.json')
    # The bad capture remains incomplete/failed; byte-identical observation is
    # sufficient to inspect its state, not to declare that game boot successful.
    p=blocks((control_state/'frame-00723.savestate').read_bytes())
    b=blocks((bad_state/'frame-00800.savestate').read_bytes())
    late=blocks((bad_state/'frame-03118.savestate').read_bytes())
    def ppu(x):
        return dict(inidisp=x['FIL'][0x2100],main_screen=x['FIL'][0x212c],
                    # Snapshot.cpp version12 serializes VMA/WRAM/BG fields
                    # then six byte fields: CGDATA starts at byte64, big-endian.
                    first16_cgram=x['PPU'][64:96].hex(),prepared_palette=x['RAM'][0x5400:0x5420].hex())
    diagnosis=dict(parent=ppu(p),failed800=ppu(b),failed3118=ppu(late),
        full_vram_equal=p['VRA']==b['VRA']==late['VRA'],prepared_palette_equal=ppu(p)['prepared_palette']==ppu(b)['prepared_palette'],
        failure_retained=True,explanation='All tile data and prepared palette exist, but INIDISP80 and main-screen00 remain latched. '
        'CGRAM remains at the settings colors. The unchanged251-line final gate starves the now palette-only batch '
        'after early OAM/full scanning; allowing its three already-spent OAM lines fixes fresh boot.')
    if not diagnosis['full_vram_equal'] or not diagnosis['prepared_palette_equal'] or any(
        diagnosis[k]['inidisp']!=128 or diagnosis[k]['main_screen']!=0 for k in ('failed800','failed3118')):
        raise ValueError('Different failure mechanism')
    with installed_prefix(): sp=sprites(Path('build/early-oam-final-sprite-followthrough-3483'),candidate)
    cohort=sprite_cohort(sp[2]);sources.update(sp[0]['sources'])
    mutant=deepcopy(sp[2]);target=next(g for g in mutant['generations'] if g['source_frame']==2020)
    target['first_render']=None;target['source_to_first_render_frames']=None
    missing_rejected=not sprite_cohort(mutant)['passed']
    if not missing_rejected:raise ValueError('Unrendered cohort source escaped')
    exact={}
    for name,old,new in [('health','row-resume-control-3449','row-early-final-health-3481'),
                         ('dialogue','row-resume-dialogue-control-3451','row-early-final-dialogue-3482')]:
        c,t=[Path('build')/x for x in (old,new)];exact[name]=compare(c,t)
        for root in (c,t):
            proof=bound_report(root/'report.json');sources.update(proof['sources']);sources[str(root/'report.json')]=sha(root/'report.json')
    audio,bindings=audio_and_cadence(candidate,normal,Path('build/early-final-audio-3488'));sources.update(bindings)
    d=bound_report(dma/'report.json');r=bound_report(renderer/'report.json')
    rb=bound_report(Path('build/early-final-render-observed-3490/renderer-observer.json'))
    sources.update(d['sources']);sources.update(r['sources']);sources.update(rb['sources'])
    receipt,timeline=verify_capture(normal)
    for proof in (d,r):
        if proof.get('rom_sha256',receipt['rom_sha256'])!=receipt['rom_sha256']:raise ValueError('Wrong qualification ROM')
    out.mkdir();cards=[]
    f=next(x['frame'] for x in timeline if x['phase']=='story')
    picture=normal/timeline[f-1]['frame_image']
    for label,source in [('failed',Path('build/early-oam-normal-3473/frames/frame-03119.png')),('fixed',picture)]:
        file=label+'.png';shutil.copyfile(source,out/file);sources[str(source)]=sha(source)
        cards.append(f'<figure><img src="{file}"><figcaption>{label}: '+('story deadline3119' if label=='failed' else f'fresh story frame{f}')+'</figcaption></figure>')
    paths=[Path(__file__),Path('tests/test_early_oam_final.py'),Path('tools/review_exact_row_scan.py'),
        Path('tools/review_row_publication.py'),Path('tools/early_oam_final_slack.py'),candidate/'manifest.json',
        candidate/'native-cpu.sfc',Path('.deps/snes9x-voice-2292/snapshot.cpp'),
        Path('.deps/snes9x-voice-2292/ppu.h'),dma/'report.json',renderer/'report.json',
        Path('build/early-final-render-observed-3490/renderer-observer.json'),
        Path('build/early-oam-final-sprite-followthrough-3483/sprite-events-capture.json'),
        Path('build/early-oam-final-sprite-3480/report.json')]
    sources.update({str(p):sha(p) for p in paths})
    health=next(e['after'] for e in exact['health']['publication']['2']['comparisons'] if e['identity'][1]==9)
    checks=dict(boot_complete=receipt['capture_complete'],sprite_cohort_next_frame=cohort['passed'],
        exact_window_guards=all(all(w['gates'].values()) for w in exact.values()),
        dma=d['passed'],render=r['passed'],audio=audio['audio']['passed'],cadence=audio['cadence']['passed'],
        old_health_latency_target_met=health['vram_latency']<=3)
    report=dict(checks=checks,passed=all(checks.values()),release_ready=False,physical_verified=False,
        diagnosis=diagnosis,sprite_cohort=cohort,missing_source_mutation_rejected=missing_rejected,
        exact_windows=exact,audio_and_cadence=audio,dma=d,renderer=r,rom_sha256=receipt['rom_sha256'],
        source_window_strict_comparison_report='build/early-oam-final-sprite-3480/report.json',
        sources=sources,scope=__doc__+' Historical source/counter/input equality failures remain in3480; '
        'the new cohort report proves display latency, not identical boot-driven encounters. Menu/combat/original-NES '
        'fidelity and physical acoustic acceptance are outstanding. No narrower gate constitutes goal completion.')
    (out/'index.html').write_text(f'''<!doctype html><meta charset="utf-8"><title>Early sprites: boot fixed</title>
<style>body{{background:#14202b;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}}a{{color:#9ef}}
.pair{{display:flex}}figure{{margin:8px}}img{{width:460px;image-rendering:pixelated}}pre{{white-space:pre-wrap}}</style>
<h1>Boot restored; prepared sprites reach the next frame</h1>
<p>Final palette-only admission now returns three scanlines already spent on the early544-byte sprite transfer.
The actual row/DMA safety gates remain checked. Candidate{receipt['rom_sha256'][:12]}, offline only.</p>
<div class="pair">{''.join(cards)}</div><h2>Cause, not missing graphics</h2>
<p>Failed and working story states have identical full VRAM and prepared palettes. The failure remains forced blank
(INIDISP80, main-screen00) and never publishes the story palette. The corrected deadline reaches the story and completes
{receipt['frames']} route frames.</p>
<h2>Actual qualification</h2><pre>{json.dumps(checks,indent=2)}</pre>
<p>{len(cohort['generations'])} original-window sprite generations all render next frame. The old trace ended at the last source;
four additional display frames now prove its publication. Later generations and the final censored source remain recorded.
Deleting the last target publication fails the gate. Historical cross-ROM timeline failures are not erased.</p>
<p>{d['dma_transfers']} full DMA envelopes checked, latest visible end line{d['latest_visible_end']};
{r['eligible_frames']} eligible renderer frames. General DMA only, not per-byte hardware or HDMA certification.</p>
<p>Health delay is still{health['vram_latency']}frames versus the older3-frame control. Menu/combat and physical audio
qualification remain open. Correct DSP restart timing is not a pop-free verdict.</p>
<audio controls src="../{normal.name}/audio.wav"></audio>
<p><a href="report.json">Complete source chains, failures, cohorts, native audio metrics and bindings</a>.</p>''')
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Changed audit source')
    report['seconds']=time.monotonic()-started
    report['artifacts']={p.name:sha(p) for p in out.iterdir() if p.is_file()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(checks=checks,seconds=report['seconds'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    review(**vars(p.parse_args()))
