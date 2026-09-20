"""Retain the broader failures that prevent promotion of focused row-scan improvements."""
import argparse
import json
from pathlib import Path
import shutil
import time

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.review_exact_row_scan import compare
from tools.review_row_publication import audio_and_cadence


def review(out):
    started=time.monotonic()
    if out.exists():raise ValueError('Fresh follow-up required')
    focused=Path('build/exact-row-scan-review-3465')
    fp=bound_report(focused/'report.json')
    sprite=Path('build/half-row-scan-sprite-cycle-3464')
    sp=bound_report(sprite/'report.json')
    qualification,sources=audio_and_cadence(Path('build/half-row-scan-game-3458'),
        Path('build/half-row-scan-normal-3462'),Path('build/half-row-scan-audio-3463'))
    sources.update(fp['sources']);sources.update(sp['sources'])
    early={};pairs=[('health','row-resume-control-3449','row-resume-early-palette-3470'),
                   ('dialogue','row-resume-dialogue-control-3451','row-resume-dialogue-early-palette-3471')]
    for name,old,new in pairs:
        c,t=[Path('build')/x for x in (old,new)]
        early[name]=compare(c,t)
        for root in (c,t):
            r=bound_report(root/'report.json');sources.update(r['sources']);sources[str(root/'report.json')]=sha(root/'report.json')
    boot=Path('build/early-oam-normal-3473');receipt=json.loads((boot/'capture.json').read_text())
    timeline=json.loads((boot/'timeline.json').read_text())
    if (sha(boot/'timeline.json')!=receipt['timeline_sha256'] or sha(boot/'audio.wav')!=receipt['audio_sha256']
        or receipt['capture_complete'] or len(timeline)!=3119 or timeline[-1]['phase']!='wait_story'):
        raise ValueError('Different incomplete boot evidence')
    image=boot/timeline[-1]['frame_image']
    if sha(image)!=timeline[-1]['frame_image_sha256']:raise ValueError('Changed terminal picture')
    # Incomplete capture intentionally is not passed to a complete-route verifier.
    # Preserve its failure rather than relaxing that verifier's precondition.
    rejected=Path('build/row-resume-early-oam-3467');bad=bound_report(rejected/'report.json')
    sources.update(bad['sources'])
    for p in (Path(__file__),Path('tools/review_exact_row_scan.py'),Path('tools/review_row_publication.py'),
              focused/'report.json',sprite/'report.json',boot/'capture.json',boot/'timeline.json',boot/'audio.wav',
              image,rejected/'report.json',Path('build/early-oam-palette-game-3469/manifest.json'),
              Path('build/early-oam-palette-game-3469/native-cpu.sfc')):
        sources[str(p)]=sha(p)
    out.mkdir();shutil.copyfile(image,out/'boot-failure.png')
    failed_picture=rejected/'frames/frame-08233.png';shutil.copyfile(failed_picture,out/'missing-palette-mode.png')
    sources[str(failed_picture)]=sha(failed_picture)
    report=dict(passed=False,release_ready=False,physical_verified=False,focused_report=str(focused),
        half_scan_sprite=sp,half_scan_audio_and_cadence=qualification,early_oam_focused=early,
        early_oam_boot=dict(complete=False,frames=len(timeline),last_phase=timeline[-1]['phase'],
            faults=[dict(frame=r['frame'],fault=r['fault']) for r in timeline if r['fault']],
            reason='Story image not reached within existing scenario deadline; black terminal picture'),
        retained_failed_early_oam='3466: moving OAM removed palette DMA mode/bank initialization; fixed separately in3469',
        sources=sources,scope=__doc__)
    counts=sp['trial']['source_to_first_render_histogram']
    (out/'index.html').write_text(f'''<!doctype html><meta charset="utf-8"><title>Row scan: not promoted</title>
<style>body{{background:#14202b;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}}a{{color:#9ef}}
.pair{{display:flex}}figure{{margin:8px}}img{{width:384px;image-rendering:pixelated}}</style>
<h1>Focused improvements found; broader gates still reject promotion</h1>
<p><a href="../{focused.name}/">Exact-state comparison collage</a>:64-entry scanning improves text and preserves both tested playfields.
The wider sprite window catches two2-frame sprite publications: {counts}. No generation omitted, but next-frame gate fails.
Source frames/encounters also differ from the historical prefix comparator; all strict failures remain.</p>
<p>Fresh half-scan full route:{qualification['frames']} frames. Busy-inclusive cadence:{qualification['cadence']['passed']}.
DSP restart timing:{qualification['audio']['passed']}, {qualification['audio']['restarts']} restarts.
These guards do not override failed sprites or certify acoustic fidelity.</p>
<h2>Sprite-first experiment</h2><p>Explicitly initializing palette DMA mode/bank fixes the first local palette corruption.
With that correction, both exact-state gameplay windows preserve playfield pixels and counters; dialogue delay is2–3 frames,
health5 instead of7. But fresh boot fails to reach the story image after3119 frames, ending black without adapter fault.
It is rejected, not a release candidate. The cause of the fresh-boot failure remains unproven.</p>
<div class="pair"><figure><img src="missing-palette-mode.png"><figcaption>Retained failed palette-mode prototype</figcaption></figure>
<figure><img src="boot-failure.png"><figcaption>Corrected palette setup, but fresh boot still fails</figcaption></figure></div>
<p>No production/default ROM, MiSTer or OBS state changed. Next work must preserve boot/transition behavior while avoiding
sprite starvation; merely increasing scan counts is insufficient.</p>
<p><a href="report.json">Complete reports, failures, source bindings and native-audio metrics</a>.</p>''')
    report['seconds']=time.monotonic()-started
    report['artifacts']={p.name:sha(p) for p in out.iterdir() if p.is_file()}
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Changed follow-up source')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=False,frames=qualification['frames'],audio=qualification['audio']['passed'],
                         cadence=qualification['cadence']['passed'],seconds=report['seconds'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    review(**vars(p.parse_args()))
