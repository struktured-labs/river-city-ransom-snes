"""Full-route qualification of the integrated delay13 restart-volume candidate."""
import argparse
import csv
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image
from scipy.io import wavfile

from tools.analyze_audio_bus import analyze
from tools.audit_main_display_latency import bound_report
from tools.audit_main_store_latency import parse
from tools.audit_ordinary_route_timing import cadence
from tools.audit_postpublish_keyon import load
from tools.audit_pulse_onset import parse_voice,characterize
from tools.audit_startup_pitch_game import note_windows,cross_game
from tools.benchmark_report import sha,verify_capture
from tools.capture_combat_instructions import equivalent
from tools.capture_sprite_prefix import installed_prefix
from tools.review_restart_volume import first_volume_failures
from tools.frame_audit import verify_frame
from tools.park_waypoints import cursor_mask


def prefix_fields(full,short,cursor):
    """Retain a derived-field schema difference; reject any changed observation."""
    if len(full)<len(short) or not short:raise ValueError('Incomplete prefix')
    differences=[]
    for a,b in zip(full,short):
        if any(a.get(k)!=v for k,v in b.items()):raise ValueError('Changed primary prefix field')
        extra=set(a)-set(b)
        if extra:
            if extra!={'waypoint_cursor'} or a['waypoint_cursor']!=list(cursor(b)):
                raise ValueError('Unverified extra prefix field')
            differences.append(dict(frame=b['frame'],field='waypoint_cursor',prefix=None,full=a['waypoint_cursor']))
    return differences


def read(candidate,normal,observed,prefix):
    binding=bound_report(observed/'startup-game.json')
    receipt,rows=verify_capture(normal);other,seen=verify_capture(observed)
    if receipt['core_sha256']!=other['core_sha256']:raise ValueError('Different observer core')
    equivalent(receipt,rows,other,seen)
    proof,writes,_=load(observed,normal,candidate)
    traces=other['dsp_latency_observer']['traces'];regs=[0]*128;ready={}
    for r in csv.reader(Path(traces['RCR_DSP_LATENCY_TRACE']['path']).open()):
        if r[0]=='D':regs[int(r[5])]=int(r[6])
        elif r[0]=='R' and int(r[1]):ready[int(r[1])]=dict(tick=int(r[2]),registers=regs.copy())
    onsets=characterize(parse_voice(list(csv.reader(Path(binding['onset']).open())),writes),ready)
    windows,inactive=note_windows(onsets['events'],writes,ready)
    bad_volume=[];volume_margins=[]
    for e in onsets['events']:
        selected=[w for w in writes if w['packet']==e['packet'] and w['register'] in (16*e['voice'],16*e['voice']+1) and w['tick']<ready[e['packet']]['tick']]
        passed=bool(selected) and all(e['tick']+32<w['tick']<e['samples'][6]['tick'] for w in selected)
        detail=dict(packet=e['packet'],voice=e['voice'],writes=selected,
            after_silence=min((w['tick']-e['tick']-32 for w in selected),default=None),
            before_output=min((e['samples'][6]['tick']-w['tick'] for w in selected),default=None))
        volume_margins.append(detail)
        if not passed:bad_volume.append(detail)
    loops,censored=parse(csv.reader(Path(binding['main']).open()),{int(k):v for k,v in binding['points'].items()},len(rows),(candidate/'native-cpu.sfc').read_bytes())
    for loop in loops:loop['nmi_advances']=(loop['finish']['nmi']-loop['start']['nmi'])&65535
    timing=cadence(loops,rows)
    bus=analyze(list(csv.reader(Path(traces['RCR_AUDIO_BUS_TRACE']['path']).open())),length_gate=True)
    with installed_prefix('right_15'):p,short=verify_capture(prefix)
    if p['rom_sha256']!=receipt['rom_sha256']:raise ValueError('Different prefix cartridge')
    cache={}
    def cursor(row):
        key=row['frame_image_sha256']
        if key not in cache:
            cache[key]=cursor_mask(np.array(Image.open(verify_frame(prefix,row)).convert('RGB')))
        return cache[key]
    # Full routes record this derived cursor even before the first waypoint.
    # Retain it, recompute from original images, compare all original fields.
    prefix_differences=prefix_fields(rows,short,cursor)
    rate,pcm=wavfile.read(normal/'audio.wav');prate,ppcm=wavfile.read(prefix/'audio.wav')
    if rate!=32040 or rate!=prate or pcm.dtype!=np.int16 or not np.array_equal(pcm[:len(ppcm)],ppcm):raise ValueError('Full route changed native prefix PCM')
    x=pcm.astype(np.int32)
    summary=dict(rom_sha256=receipt['rom_sha256'],frames=len(rows),received_packets=proof['packets'],restarts=onsets['restarts'],
        wrong_first_pitch=onsets['wrong_first_pitch'],stale_nonzero_onsets=onsets['stale_nonzero_onsets'],
        late_volume=first_volume_failures(onsets['events']),pitch_windows=windows,
        failed_pitch_windows=[w for w in windows if not w['passed']],failed_volume_windows=bad_volume,
        volume_margins=volume_margins,kon_phases=sorted({w['kon_tick']%64 for w in windows}),
        unstaged_muted=inactive,cadence=timing,censored_main_events=censored,
        native_audio=dict(samples=len(pcm),peak=int(np.abs(x).max()),max_adjacent_step=int(np.abs(np.diff(x,axis=0)).max()),
            rms=float(np.sqrt(np.mean(x.astype(float)**2))),clipped=int(np.count_nonzero(np.any((x==-32768)|(x==32767),axis=1)))),
        prefix_existing_fields_and_pcm_exact=True,prefix_timeline_exact=not prefix_differences,
        prefix_schema_differences=prefix_differences,observer_neutral=True)
    sources={**binding['sources'],**proof['sources']}
    sources.update({str(p):sha(p) for p in (observed/'startup-game.json',normal/'audio.wav',normal/'timeline.json',prefix/'capture.json',prefix/'audio.wav')})
    return dict(summary=summary,rows=rows,bus=bus,sources=sources,core=receipt['core_sha256'])


def audit(candidate,normal,observed,parent,parent_normal,parent_observed,prefix,parent_prefix,prefix_review,renderer,render_normal,render_observed,out):
    started=time.monotonic()
    if out.exists():raise ValueError('Fresh qualification required')
    local=bound_report(prefix_review/'report.json')
    a=read(parent,parent_normal,parent_observed,parent_prefix)
    b=read(candidate,normal,observed,prefix)
    if a['core']!=b['core']:raise ValueError('Different audio cores')
    if local['trial']['rom_sha256']!=b['summary']['rom_sha256'] or not local['passed']:raise ValueError('Different/unqualified prefix')
    r=bound_report(renderer/'report.json');rb=bound_report(render_observed/'renderer-observer.json')
    rn,rr=verify_capture(render_normal);ro,rs=verify_capture(render_observed)
    if rn['core_sha256']!=ro['core_sha256'] or rn['rom_sha256']!=b['summary']['rom_sha256']:raise ValueError('Different renderer core/ROM')
    equivalent(rn,rr,ro,rs)
    cross=cross_game(a['rows'],b['rows'])
    commands=[p['bytes'] for p in a['bus']['packets']]==[p['bytes'] for p in b['bus']['packets']]
    trajectories=[]
    for x,y in zip(a['rows'],b['rows']):
        fields=[k for k in ('probe_052b','nmi_counter','input_requested','input_delivered') if x[k]!=y[k]]
        fields += [k for k in ('logical_camera_x','hdma_street_scroll_x') if x['native'].get(k)!=y['native'].get(k)]
        if fields:trajectories.append(dict(frame=x['frame'],fields=fields))
    s=b['summary']
    gate=local['passed'] and commands and not trajectories and s['cadence']['passed'] and r['passed'] and not(
        s['wrong_first_pitch'] or s['stale_nonzero_onsets'] or s['late_volume'] or s['failed_pitch_windows'] or s['failed_volume_windows'])
    sources={**a['sources'],**b['sources'],**r['sources'],**rb['sources']}
    paths=[Path(__file__),Path('tools/audit_volume_game_prefix.py'),Path('tools/audit_postpublish_keyon.py'),
        Path('tools/audit_startup_pitch_game.py'),Path('tools/audit_pulse_onset.py'),
        Path('tools/review_restart_volume.py'),Path('tools/review_startup_pitch_trial.py'),
        Path('tools/audit_main_store_latency.py'),Path('tools/audit_ordinary_route_timing.py'),
        Path('tools/audit_busy_combat.py'),prefix_review/'report.json',renderer/'report.json',render_observed/'renderer-observer.json']
    paths += [Path('tools/park_waypoints.py'),Path('tools/frame_audit.py'),Path('tests/test_volume_full_prefix.py')]
    sources.update({str(p):sha(p) for p in paths})
    out.mkdir()
    changed=sum('video_sha256' in x['fields'] for x in cross['differences'])
    hist={room:v['frame_histogram'] for room,v in s['cadence']['rooms'].items()}
    html=f'''<!doctype html><meta charset="utf-8"><title>Integrated audio / speed / scrolling</title>
<style>body{{background:#121923;color:#eef;font:18px system-ui;max-width:1050px;margin:35px auto}}a{{color:#8df}}audio{{width:100%}}pre{{white-space:pre-wrap}}</style>
<h1>Full-route integrated checks: {'PASS' if gate else 'FAIL'}</h1><p>Candidate {candidate.name}; offline emulator tests, no deployment. Original graphics unchanged.</p>
<p>{s['frames']:,} frames; {s['received_packets']:,} received sound packets. Control and trial use equal upload lengths. Command sequence equal: {commands}. Same-core observer on/off neutrality includes complete native PCM.</p>
<h2>Audio restart timing</h2><p>{s['restarts']:,} restarts; pitch-window failures {len(s['failed_pitch_windows'])}, volume-window failures {len(s['failed_volume_windows'])}, wrong first pitch {s['wrong_first_pitch']}, late volume {len(s['late_volume'])}. KON phase coverage {len(s['kon_phases'])}/64. Exact prefix PCM and all original timeline fields reproduce the earlier <a href="../{prefix_review.name}/">burst-fix test and rejected early-delay control</a>. Full-route metadata additionally includes a derived waypoint cursor; every added value was recomputed from the prefix image and retained, not treated as whole-timeline equality.</p>
<h2>Speed / scrolling</h2><p>Busy-inclusive original game-loop frame intervals by room:</p><pre>{json.dumps(hist,indent=2)}</pre><p>Counter, camera and delivered/requested input trajectory differences: {len(trajectories)} frames. Renderer: {r['eligible_frames']:,} eligible frames; missing coverage {len(r['coverage_failures'])}, split camera {len(r['splits'])}, stale camera {len(r['stale_camera_failures'])}.</p>
<h2>Full native recordings</h2><p>Control</p><audio controls preload="none" src="../{parent_normal.name}/audio.wav"></audio><p>Trial</p><audio controls preload="none" src="../{normal.name}/audio.wav"></audio>
<p>No gain, resampling, trimming, subjective-listening or pop-free claim. Maximum adjacent step {a['summary']['native_audio']['max_adjacent_step']} → {s['native_audio']['max_adjacent_step']}; native sample count {a['summary']['native_audio']['samples']} → {s['native_audio']['samples']}.</p>
<h2>Remaining limits</h2><p>{changed} image differences and {len(cross['callback_differences'])} callback differences remain recorded, not normalized away. Native source timing changes can alter the mixed waveform. This is not matched original-NES CPU work or a whole-game release certificate. Exact-build DMA, menu, additional combat and physical audio/speed acceptance remain outstanding.</p><p><a href="report.json">All measurements and source bindings</a></p>'''
    (out/'index.html').write_text(html)
    report=dict(passed=gate,baseline=a['summary'],trial=s,commands_equal=commands,
        complete_packet_records_equal=a['bus']['packets']==b['bus']['packets'],trajectory_differences=trajectories,
        cross_game=cross,renderer=r,prefix_reproduced=True,sources=sources,artifacts={'index.html':sha(out/'index.html')},
        elapsed_seconds=time.monotonic()-started,release_ready=False,physical_audio_verified=False,pop_free_verified=False,scope=__doc__)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=gate,restarts=s['restarts'],failed_pitch=len(s['failed_pitch_windows']),
        failed_volume=len(s['failed_volume_windows']),late_volume=len(s['late_volume']),phases=len(s['kon_phases']),
        cadence=hist,renderer=r['passed'],commands_equal=commands,trajectory_differences=len(trajectories),seconds=report['elapsed_seconds'])))
    if not gate:raise ValueError('Full-route integrated check failed')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','normal','observed','parent','parent-normal','parent-observed','prefix','parent-prefix','prefix-review','renderer','render-normal','render-observed','out'):
        p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
