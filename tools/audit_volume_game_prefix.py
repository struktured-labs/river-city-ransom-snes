"""Actual-game restart volume, native audio, and busy-inclusive prefix cadence."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import shutil
import time

import numpy as np
from scipy.io import wavfile

from tools.analyze_audio_bus import analyze
from tools.audit_main_display_latency import bound_report
from tools.audit_main_store_latency import parse
from tools.audit_ordinary_route_timing import cadence
from tools.audit_postpublish_keyon import load
from tools.audit_pulse_onset import parse_voice,characterize
from tools.audit_startup_pitch_game import note_windows,cross_game
from tools.benchmark_report import sha,verify_capture
from tools.capture_sprite_prefix import installed_prefix
from tools.frame_audit import verify_frame
from tools.review_restart_volume import first_volume_failures


def arm(observed,normal):
    binding=bound_report(observed/'volume-prefix.json');bound_report(normal/'volume-prefix.json')
    candidate=Path(binding['candidate'])
    with installed_prefix('right_15'):
        proof,writes,_=load(observed,normal,candidate)
        receipt,rows=verify_capture(normal)
    if not binding['observer_neutral'] or sha(Path(binding['core']))!=receipt['core_sha256']:
        raise ValueError('Missing same-core control')
    regs=[0]*128;ready={}
    records=list(csv.reader(Path(binding['traces']['RCR_DSP_LATENCY_TRACE']).open()))
    for row in records:
        if row[0]=='D':regs[int(row[5])]=int(row[6])
        elif row[0]=='R' and int(row[1]):ready[int(row[1])]=dict(tick=int(row[2]),registers=regs.copy())
    onsets=characterize(parse_voice(list(csv.reader(Path(binding['traces']['RCR_PULSE_ONSET_TRACE']).open())),writes),ready)
    windows,inactive=note_windows(onsets['events'],writes,ready)
    labels={r.split()[2].lstrip('.'):int(r.split()[1],16) for r in (candidate/'native_runtime.lbl').read_text().splitlines()}
    points={0:labels['gameplay_iteration_start'],1:0xf282,2:labels['camera_deferred_nmi_exit']+2,3:0xf2da}
    loops,censored=parse(csv.reader(Path(binding['traces']['RCR_MAIN_STORE_TRACE']).open()),points,len(rows),(candidate/'native-cpu.sfc').read_bytes())
    for loop in loops:loop['nmi_advances']=(loop['finish']['nmi']-loop['start']['nmi'])&65535
    timing=cadence(loops,rows)
    bus=analyze(list(csv.reader(Path(binding['traces']['RCR_AUDIO_BUS_TRACE']).open())),length_gate=True)
    # Freeze the packet from the pre-existing game defect, not a new favorable
    # event selected by the candidate's waveform. Identity checked across arms.
    target=next(e for e in onsets['events'] if e['packet']==2845 and e['voice']==1)
    early_regs=[0]*128
    for w in writes:
        if w['packet']>=2845:break
        early_regs[w['register']]=w['value']
    volume_writes=[w for w in writes if w['packet']==2845 and w['register'] in (16,17) and w['tick']<ready[2845]['tick']]
    if early_regs[16:18]!=[0,0] or target['target_volumes']!=[120,120]:raise ValueError('Changed target unmute case')
    silent=target['tick']+32
    early=[w for w in volume_writes if w['value'] and w['tick']<=silent]
    rate,pcm=wavfile.read(normal/'audio.wav')
    if rate!=32040 or pcm.dtype!=np.int16 or pcm.ndim!=2 or pcm.shape[1]!=2:raise ValueError('Wrong native PCM')
    late=first_volume_failures(onsets['events'])
    # Volume stores must be in startup silence too, not just correct eventually.
    volume_windows=[]
    for event in onsets['events']:
        v=event['voice'];packet=event['packet']
        selected=[w for w in writes if w['packet']==packet and w['register'] in (16*v,16*v+1) and w['tick']<ready[packet]['tick']]
        volume_windows.append(dict(packet=packet,voice=v,writes=selected,silent_from=event['tick']+32,
            first_output=event['samples'][6]['tick'],
            passed=bool(selected) and all(event['tick']+32<w['tick']<event['samples'][6]['tick'] for w in selected)))
    x=pcm.astype(np.int32)
    summary=dict(rom_sha256=receipt['rom_sha256'],frames=len(rows),packets=proof['packets'],
        restarts=onsets['restarts'],wrong_first_pitch=onsets['wrong_first_pitch'],stale_nonzero_onsets=onsets['stale_nonzero_onsets'],
        late_volume=late,pitch_windows=windows,failed_pitch_windows=[w for w in windows if not w['passed']],
        volume_windows=volume_windows,failed_volume_windows=[w for w in volume_windows if not w['passed']],
        unstaged_muted=inactive,kon_phases=sorted({w['kon_tick']%64 for w in windows}),
        cadence=timing,censored_main_events=censored,
        target=dict(packet=2845,voice=1,initial_volumes=early_regs[16:18],event=target,
            volume_writes=volume_writes,unmute_before_silence=early),
        native_audio=dict(samples=len(pcm),peak=int(np.abs(x).max()),rms=float(np.sqrt(np.mean(x.astype(float)**2))),
            max_adjacent_step=int(np.abs(np.diff(x,axis=0)).max()),clipped=int(np.count_nonzero(np.any((x==-32768)|(x==32767),axis=1)))))
    sources={**binding['sources'],**proof['sources']}
    sources.update({str(p):sha(p) for p in (observed/'volume-prefix.json',normal/'volume-prefix.json',normal/'timeline.json',normal/'audio.wav')})
    return dict(summary=summary,sources=sources,rows=rows,bus=bus,pcm=pcm,core=receipt['core_sha256'])


def audit(before,normal_before,after,normal_after,rejected,normal_rejected,state,out):
    started=time.monotonic()
    if out.exists():raise ValueError('Fresh game audit required')
    a,b,failed=[arm(o,n) for o,n in ((before,normal_before),(after,normal_after),(rejected,normal_rejected))]
    stateproof=bound_report(state/'report.json')
    if not a['core']==b['core']==failed['core']:raise ValueError('Different game cores')
    cross=cross_game(a['rows'],b['rows'])
    commands_equal=[p['bytes'] for p in a['bus']['packets']]==[p['bytes'] for p in b['bus']['packets']]
    records_equal=a['bus']['packets']==b['bus']['packets']
    trajectories=[]
    for x,y in zip(a['rows'],b['rows']):
        fields=[k for k in ('probe_052b','nmi_counter','input_requested','input_delivered') if x[k]!=y[k]]
        fields += [k for k in ('logical_camera_x','hdma_street_scroll_x') if x['native'].get(k)!=y['native'].get(k)]
        if fields:trajectories.append(dict(frame=x['frame'],fields=fields))
    current=b['summary']
    timing=current['cadence'];present={k for k,v in timing['rooms'].items() if v['intervals']}
    # The full four-room gate is deliberately retained as false; this prefix
    # reaches only rooms0/1. No unsupported room is silently counted as tested.
    cadence_pass=present=={'0','1'} and all(v['passed'] for v in timing['rooms'].values() if v['intervals'])
    negatives=dict(early_delay_rejected=bool(failed['summary']['failed_pitch_windows']),
        original_unmute_rejected=bool(a['summary']['target']['unmute_before_silence']))
    passed=bool(stateproof['passed']) and commands_equal and not trajectories and cadence_pass and not(
        current['wrong_first_pitch'] or current['stale_nonzero_onsets'] or current['late_volume'] or
        current['failed_pitch_windows'] or current['failed_volume_windows'] or current['target']['unmute_before_silence']) and all(negatives.values())
    out.mkdir();sources={**a['sources'],**b['sources'],**failed['sources'],**stateproof['sources']}
    changed=[r['frame'] for r in cross['differences'] if 'video_sha256' in r['fields']]
    cards=[]
    for frame in changed[:4]:
        cards.append(f'<h3>First changed frame {frame}</h3><div class="pair">')
        for label,root,data in [('control',normal_before,a),('trial',normal_after,b)]:
            path=verify_frame(root,data['rows'][frame-1]);sources[str(path)]=sha(path)
            name=f'{frame}-{label}.png';shutil.copyfile(path,out/name)
            cards.append(f'<figure><img src="{name}"><figcaption>{label}</figcaption></figure>')
        cards.append('</div>')
    center=a['summary']['target']['event']['keyon_write']['tick']//32
    lo,hi=center-16020,center+16020
    clips=[]
    for name,data in [('control',a),('trial',b)]:
        if not 0<=lo<hi<=len(data['pcm']):raise ValueError('Missing native target clip')
        wavfile.write(out/(name+'.wav'),32040,data['pcm'][lo:hi])
        rate,check=wavfile.read(out/(name+'.wav'))
        if rate!=32040 or not np.array_equal(check,data['pcm'][lo:hi]):raise ValueError('Changed native excerpt')
        clips.append(dict(arm=name,first=lo,last=hi,same_absolute_samples=True))
    html=f'''<!doctype html><meta charset="utf-8"><title>Actual game restart-volume prefix</title>
<style>body{{background:#151b25;color:#eef;font:17px system-ui;max-width:1150px;margin:30px auto}}a{{color:#8df}}.pair{{display:flex}}figure{{margin:8px;flex:1}}img{{width:100%;image-rendering:pixelated}}audio{{width:100%}}</style>
<h1>Actual game audio prefix: {'PASS' if passed else 'FAIL'}</h1>
<p>Integrated engine, offline only. 3,419-frame boot/input replay through right_15, not the full park route. No MiSTer/OBS action. Both arms upload the same 12,608 bytes; control uses original sound logic plus padding.</p>
<p>{current['packets']:,} received packets; identical command sequence: {commands_equal}. {current['restarts']} restarts: {len(current['failed_pitch_windows'])} pitch-window failures, {len(current['failed_volume_windows'])} volume-window failures, {len(current['late_volume'])} late volumes, {current['wrong_first_pitch']} wrong first pitches.</p>
<p>The rejected delay8 game has {len(failed['summary']['failed_pitch_windows'])} pitch-window failures, despite correct first pitch. Delay13 keeps every tested pitch and volume store inside observed startup silence. Covered KON phases: {len(current['kon_phases'])}/64; not presumed exhaustive.</p>
<h2>Original target: packet2845, pulse2</h2><p>Control unmutes the old oscillator before silent startup: {len(a['summary']['target']['unmute_before_silence'])} writes. Trial: {len(current['target']['unmute_before_silence'])}. Both start with volume0 and request120. The trial's unchanged zero-volume registers rule out this voice's old-wave burst; other voices remain audible. This is not an assertion that the user's physical pop is eliminated.</p>
<p>Untouched native full-mix clips use the same absolute sample interval, no alignment, gain or resampling.</p><p>Control</p><audio controls preload="none" src="control.wav"></audio><p>Trial</p><audio controls preload="none" src="trial.wav"></audio>
<h2>Speed and strict differences</h2><p>Busy-inclusive two-frame cadence in sampled rooms0/1: {cadence_pass}. Original counter, camera and requested/delivered input trajectories differ on {len(trajectories)} frames. Missing rooms2/3 remain unqualified; the full four-room gate is {timing['passed']}.</p>
<p>{len(changed)} changed images; {len(cross['differences'])} nonaudio timeline differences, {len(cross['callback_differences'])} callback differences. All retained, including transition images and scratch/stack differences. This is not full timing or renderer equivalence.</p>{''.join(cards)}
<p>Native full-mix maximum step: {a['summary']['native_audio']['max_adjacent_step']} → {current['native_audio']['max_adjacent_step']}. Global popping, original-NES fidelity, full route/combat, DMA, menus and hardware acceptance remain open.</p>
<p><a href="report.json">Full measurements, failures and source bindings</a></p>'''
    (out/'index.html').write_text(html)
    paths=[Path(__file__),Path('tools/capture_volume_game_prefix.py'),Path('tools/audit_startup_pitch_game.py'),
        Path('tools/audit_pulse_onset.py'),Path('tools/audit_postpublish_keyon.py'),Path('tools/review_restart_volume.py'),
        Path('tools/review_startup_pitch_trial.py'),Path('tools/audit_main_store_latency.py'),
        Path('tools/audit_ordinary_route_timing.py'),Path('tools/audit_busy_combat.py'),state/'report.json']
    sources.update({str(p):sha(p) for p in paths})
    report=dict(passed=passed,baseline=a['summary'],trial=current,rejected_delay8=failed['summary'],
        cross_game=cross,commands_equal=commands_equal,complete_packet_records_equal=records_equal,
        trajectory_differences=trajectories,sampled_room_cadence_passed=cadence_pass,negative_controls=negatives,
        clips=clips,sources=sources,artifacts={p.name:sha(p) for p in out.iterdir() if p.is_file()},
        elapsed_seconds=time.monotonic()-started,release_ready=False,physical_audio_verified=False,pop_free_verified=False,scope=__doc__)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=passed,restarts=current['restarts'],failed_pitch=len(current['failed_pitch_windows']),
        failed_volume=len(current['failed_volume_windows']),late_volume=len(current['late_volume']),
        commands_equal=commands_equal,trajectory_differences=len(trajectories),cadence=cadence_pass,
        kon_phases=len(current['kon_phases']),changed_images=len(changed),seconds=report['elapsed_seconds'])))
    if not passed:raise ValueError('Actual game prefix qualification failed')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('before','normal-before','after','normal-after','rejected','normal-rejected','state','out'):
        p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
