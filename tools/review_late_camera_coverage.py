"""Qualify extended recorder coverage without hiding sprite/audio observer effects."""
import argparse
import csv
import html
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image

from tools.audit_camera_export_episode import measure
from tools.audit_camera_log_coordinates import compare as compare_lines
from tools.audit_main_display_latency import bound_report
from tools.audit_scroll_splits import eligible
from tools.benchmark_report import sha, verify_capture
from tools.camera_state_log import decode
from tools.review_wait_camera_log import compare


def coverage(records):
    measured=measure(records)
    adjacent=[p for p in measured['pairs'] if p['nmi_ticks']==2 and p['same_room']]
    return dict(samples=len(records),two_tick_pairs=len(adjacent),
        moving_two_tick_pairs=sum(p['working_delta']!=0 for p in adjacent),
        gaps=len(measured['unobserved_intervals']),
        max_gap_nmi=max(p['nmi_ticks'] for p in measured['pairs']),
        interrupted_samples=measured['interrupted_samples'])


def audit(normal,early,late,parent_renderer,late_renderer,boundary,control_boundary,out):
    if out.exists():raise ValueError('Fresh output required')
    paths=(Path(__file__),Path('tools/audit_camera_export_episode.py'),
        Path('tools/audit_camera_log_coordinates.py'),Path('tools/audit_scroll_splits.py'),
        Path('tools/review_wait_camera_log.py'),Path('tools/camera_state_log.py'),
        Path('tools/audio_packet_log.py'),Path('tests/test_late_camera_coverage.py'))
    sources={str(p):sha(p) for p in paths}
    def bound(path):
        report=bound_report(path)
        sources.update(report['sources']);sources[str(path)]=sha(path)
        return report
    matrices=[bound(p/'report.json') for p in (control_boundary,boundary)]
    for r,cutoff in zip(matrices,(194,230)):
        if (not r['passed'] or r['cutoff']!=cutoff or r['quick'] or len(r['cases'])!=168 or
                len(r['mutants'])!=4 or any(m['passed'] for m in r['mutants'])):
            raise ValueError('Need both full matrices and rejected mutants')
    base,left=verify_capture(normal)
    for name in ('capture.json','timeline.json','audio.wav'):sources[str(normal/name)]=sha(normal/name)
    results={};coverages={};pictures={}
    for name,folder in (('early',early),('late',late)):
        proof=bound(folder/'logger-report.json')
        receipt,right=verify_capture(folder)
        if any(base[k]!=receipt[k] for k in ('scenario_sha256','core_sha256')):
            raise ValueError('Different replay/core')
        meta_paths=[Path(p) for p in proof['sources'] if p.endswith('/manifest.json')]
        if len(meta_paths)!=1:raise ValueError('Ambiguous cartridge manifest')
        meta=json.loads(meta_paths[0].read_text())
        for key in ('diagnostic_camera_log','camera_idle_log','idle_camera_branch_repair','camera_wait_log','late_camera_log'):
            for p,h in meta.get(key,{}).get('sources',{}).items():
                if sha(Path(p))!=h:raise ValueError('Changed diagnostic dependency: '+p)
                sources[p]=h
        matrix=matrices[0 if name=='early' else 1]
        roms=[p for p in matrix['sources'] if p.endswith('/native-cpu.sfc')]
        if len(roms)!=1 or matrix['sources'][roms[0]]!=receipt['rom_sha256']:
            raise ValueError('Boundary ROM differs from gameplay ROM')
        result=compare(left,right)
        result.update(complete=receipt['capture_complete'],frames=len(right),
            fault_frames=sum(bool(r['fault']) for r in right),
            pcm_exact=receipt['audio_sha256']==base['audio_sha256'])
        result['fully_neutral']=result['timeline_exact'] and result['pcm_exact']
        results[name]=result
        data=(folder/'camera.srm').read_bytes()
        decoded=decode(data)
        if decoded!=json.loads((folder/'camera.json').read_text()):
            raise ValueError('Changed camera derivation')
        coverages[name]=coverage(decoded['records'])
        # Retain all changed-picture regions; collage only the first three.
        pixel=[]
        for frame in result['video_differences']:
            arrays=[]
            for capture,rows in ((normal,left),(folder,right)):
                p=capture/f'frames/frame-{frame:05d}.png'
                if sha(p)!=rows[frame-1]['frame_image_sha256']:
                    raise ValueError('Changed frame picture')
                sources[str(p)]=sha(p)
                with Image.open(p) as image:arrays.append(np.asarray(image.convert('RGB')))
            yy,xx=np.where(np.any(arrays[0]!=arrays[1],axis=2))
            pixel.append(dict(frame=frame,pixels=len(xx),bounds=[int(xx.min()),int(yy.min()),int(xx.max()),int(yy.max())]))
        pictures[name]=pixel
    if not all(r['complete'] and r['camera_fields_exact'] and r['input_and_phase_exact'] for r in results.values()):
        raise ValueError('Recorder changes route/camera observations')
    traces=[]
    for folder,expected in ((parent_renderer,base['rom_sha256']),(late_renderer,receipt['rom_sha256'])):
        proof=bound(folder/'renderer-observer.json')
        observation=json.loads((folder/'capture.json').read_text())
        if not proof['observer_neutral'] or proof['frames']!=base['frames'] or observation['rom_sha256']!=expected:
            raise ValueError('Renderer not qualified for the compared cartridge')
        traces.append(Path(proof['trace']))
    selected={r['frame'] for p,r in zip(left,left[1:]) if eligible(p) and eligible(r)}
    with traces[0].open() as a,traces[1].open() as b:
        rendered=compare_lines(csv.DictReader(a),csv.DictReader(b),selected)
    for p in traces:sources[str(p)]=sha(p)
    out.mkdir(parents=True)
    cards=[]
    for name,folder in (('early',early),('late',late)):
        for frame in results[name]['video_differences'][:3]:
            cards.append(f'<p>{name}, frame {frame}: regular then recorder</p><div class="pair">')
            for label,capture in (('normal',normal),(name,folder)):
                filename=f'{name}-{label}-{frame}.png'
                shutil.copyfile(capture/f'frames/frame-{frame:05d}.png',out/filename)
                cards.append(f'<img src="{filename}">')
            cards.append('</div>')
    report=dict(coverage=coverages,comparisons=results,pixel_changes=pictures,renderer=rendered,
        boundary_max_masked_clocks=max(c['masked_clocks'] or 0 for c in matrices[1]['cases']),
        camera_only_passed=rendered['eligible_camera_match'],full_observer_neutral=False,
        physical_deployed=False,release_ready=False,sources=sources,
        scope='Same complete route and inputs; exact camera/tick frame-end fields plus keyed actual renderer scanlines. '
        'All sprite-picture and PCM differences remain failures of full neutrality. Coverage counts only adjacent '
        'two-NMI samples in the same room, with nonzero working-camera change; gaps are not interpolated. '
        'Boundary fixture has minimal interrupt handler, not whole-game worst-case timing. Offline only; '
        'no physical hold attribution, speed or audio certification.')
    summary=dict(coverage=coverages,eligible_camera_match=rendered['eligible_camera_match'],
        eligible_frames=rendered['eligible_frames'],renderer_differences=len(rendered['differences']),
        boundary_max_masked_clocks=report['boundary_max_masked_clocks'],
        video_differences={k:len(v['video_differences']) for k,v in results.items()},
        pcm_exact={k:v['pcm_exact'] for k,v in results.items()})
    page='<!doctype html><meta charset="utf-8"><title>Extended camera recorder coverage</title><style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}a{color:#8df}pre{white-space:pre-wrap}.pair{display:flex}.pair img{width:48%;image-rendering:pixelated}</style>'
    page+='<h1>Extended camera recording window — offline qualification</h1><p>'+html.escape(report['scope'])+'</p>'
    page+='<pre>'+html.escape(json.dumps(summary,indent=2))+'</pre><h2>Retained picture differences</h2>'+''.join(cards)
    page+='<p><a href="report.json">Every difference, gap summary and evidence hash</a> · <a href="../camera-hardware-review-2546/">Physical coverage limitation that motivated this trial</a></p>'
    (out/'index.html').write_text(page)
    report['artifacts']={p.name:sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(summary))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('normal','early','late','parent-renderer','late-renderer','boundary','control-boundary','out'):
        p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
