"""Publish measured pause latency and rejected scheduling trials without a fix claim."""
import argparse
import csv
import html
import json
from pathlib import Path
import shutil

from tools.audit_main_display_latency import bound_report
from tools.audit_park_instructions import parse
from tools.benchmark_report import sha, verify_capture
from tools.check_present_status import compare

ROOT=Path('build/overflow-3526')


def review(out):
    if out.exists():raise ValueError('Fresh report required')
    sources={str(Path(__file__)):sha(Path(__file__))}
    def bind(p):
        sources[str(p)]=sha(p)
    def bound(p):
        r=bound_report(p);sources.update(r['sources']);bind(p);return r
    timing=bound(Path('build/mixed-pause-audio-3608/report.json'))
    parent_timing=bound(Path('build/parent-pause-audio-3611/report.json'))
    observation=bound(ROOT/'mixed-pause-observed-3612/pause-observer.json')
    if timing['passed'] or parent_timing['passed'] or not observation['observer_neutral']:
        raise ValueError('Expected retained failing timings and neutral observation')
    captures={}
    for name,folder in (
        ('nes',Path('build/status-nes-167')),
        ('working',ROOT/'mixed-pause-status-3607'),
        ('observed',ROOT/'mixed-pause-observed-3612'),
        ('mapped_trial',ROOT/'paused-audio-bank-status-3618'),
        ('preserved_trial',ROOT/'paused-audio-preserved-status-3622'),
        ('preserved_observed',ROOT/'paused-audio-preserved-boot-observed-3623')):
        receipt,rows=verify_capture(folder)
        captures[name]=(receipt,rows,folder)
        for f in ('capture.json','timeline.json','audio.wav'):bind(folder/f)
    for left,right in (('working','observed'),('preserved_trial','preserved_observed')):
        a,rowsa,_=captures[left];b,rowsb,_=captures[right]
        if rowsa!=rowsb or any(a[k]!=b[k] for k in
                ('core_sha256','rom_sha256','frames','audio_sha256','scenario_sha256','capture_complete')):
            raise ValueError('Observer changed full captured execution or PCM')
    if not captures['working'][0]['capture_complete'] or any(captures[k][0]['capture_complete']
            for k in ('mapped_trial','preserved_trial')):
        raise ValueError('Unexpected boot outcome')
    statuses=compare(captures['nes'][2],captures['working'][2])
    if not all(x['passed'] for x in statuses):raise ValueError('Working status oracle failed')
    for f in ('tools/check_present_status.py','tools/audit_park_instructions.py',
              'tools/benchmark_report.py','tools/audit_main_display_latency.py'):
        bind(Path(f))
    trace=Path(observation['traces']['RCR_INSTRUCTION_TRACE'])
    with trace.open() as f:instructions=parse(csv.reader(f),1430,1440)
    def event(pc,frame):
        found=[r for r in instructions if r['pc']==pc and r['frame']==frame]
        if len(found)!=1:raise ValueError('Ambiguous instruction event')
        return found[0]
    cue=event(0xc680fc,1435)
    state=event(0xc7f799,1435)
    driver=event(0xc1fa54,1435)
    if not state['clock']<cue['clock']<driver['clock'] or state['a']&255!=0xa0:
        raise ValueError('Changed cue/driver order')
    bus=Path(observation['traces']['RCR_AUDIO_BUS_TRACE'])
    with bus.open() as f:
        writes=[r for r in csv.reader(f) if r[0]=='W' and r[4]=='1046']
    if not writes or min(int(r[1]) for r in writes)!=1435 or max(int(r[1]) for r in writes)!=1436:
        raise ValueError('Expected cross-frame source APU writes')
    failed_trace=ROOT/'paused-audio-preserved-boot-observed-3623.csv'
    bind(failed_trace)
    with failed_trace.open() as f:failed_instructions=parse(csv.reader(f),535,545)
    helper=[r for r in failed_instructions if r['pc']==0xd900]
    returns=[r for r in failed_instructions if r['pc']==0xd93f]
    if len(helper)!=11 or len(returns)!=11 or any(r['pc']==0xc15f00 for r in failed_instructions):
        raise ValueError('Expected eleven nonservicing helper calls during rejected boot')
    for a,b in zip(helper,returns):
        if (a['frame'],a['a'],a['s'])!=(b['frame'],b['a'],b['s']):
            raise ValueError('Accumulator/return-stack not preserved')
    for folder in ('consumer-mixed-game-3583','paused-prepublication-game-3613',
                   'paused-audio-bank-game-3617','paused-audio-preserved-game-3621'):
        manifest=Path('build')/folder/'manifest.json'
        m=json.loads(manifest.read_text());rom=manifest.parent/'native-cpu.sfc'
        if sha(rom)!=m['rom_sha256']:raise ValueError('Changed cartridge')
        bind(manifest);bind(rom)
        for k in ('experimental_paused_prepublication_audio','experimental_paused_audio_preserved'):
            if k in m:
                for p,h in m[k]['sources'].items():
                    if sha(Path(p))!=h:raise ValueError('Changed trial source')
                    sources[p]=h
    summary=dict(working_rom=captures['working'][0]['rom_sha256'],
        pause_onset=dict(nes=timing['nes']['frame_offset'],working=timing['snes']['frame_offset'],
            parent=parent_timing['snes']['frame_offset']),
        menu_state_store=state,cue_pointer_store=cue,driver_entry=driver,
        source_write_rows=writes,source_to_driver_master_clocks=driver['clock']-cue['clock'],
        neutral_instruction_observation_frames=len(captures['working'][1]),
        status_checks=statuses,
        rejected=[dict(name=k,frames=captures[k][0]['frames'],
            complete=captures[k][0]['capture_complete'],last_phase=captures[k][1][-1]['phase'])
            for k in ('mapped_trial','preserved_trial')],
        failed_boot_observer_neutral=True,failed_boot_observed_frames=2940,
        observed_nonservicing_helper_calls=len(helper),
        native_timing_controls=timing['controls'])
    out.mkdir(parents=True)
    media=(
        (Path('build/mixed-pause-audio-3608/nes.wav'),'nes.wav'),
        (Path('build/mixed-pause-audio-3608/snes.wav'),'working.wav'),
        (captures['working'][2]/'settings.png','working-settings.png'),
        (captures['preserved_trial'][2]/'wait_settings.png','rejected-settings.png'),
        (captures['working'][2]/'status_visible.png','working-status.png'),
        (captures['nes'][2]/'status_visible.png','nes-status.png'))
    for source,name in media:
        bind(source);shutil.copyfile(source,out/name)
        if sha(source)!=sha(out/name):raise ValueError('Changed exported media')
    body='''<!doctype html><meta charset="utf-8"><title>Pause audio scheduling investigation</title>
<style>body{background:#101821;color:#eef;font:17px system-ui;max-width:1040px;margin:28px auto}
a{color:#9df}.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}img{width:100%;image-rendering:pixelated}
figure{margin:4px}audio{width:100%}td{padding:8px;border-bottom:1px solid #456}</style>
<h1>Pause audio: one-frame delay traced; proposed move rejected</h1>
<p>No new build is promoted or deployed. Working candidate3583 remains unchanged.</p>
<table><tr><td>Separated pause sound onset</td><td>NES offset57; parent3527 and working3583 offset58</td></tr>
<tr><td>Same-core observation</td><td>All2535 captured frames and native PCM identical with tracing enabled</td></tr>
<tr><td>Cue → original sound driver</td><td>Frame1435 line58 → line256; source APU writes spill into1436</td></tr>
<tr><td>Present Status</td><td>Opening/reopening digits and checked pixels match the original NES oracle</td></tr></table>
<p>The trace contradicts the first hypothesis that the driver runs before the cue. It instead shows late
service and cross-frame source writes. This is a specific onset defect, not attribution of every pop or
proof of NES waveform fidelity.</p>
<h2>Unmodified native pause clips</h2><div class="pair"><div>Original NES<audio controls src="nes.wav"></audio></div>
<div>Working SNES3583<audio controls src="working.wav"></audio></div></div>
<p>Input-relative120-frame excerpts, native rates and gain. No resampling, alignment or normalization.
Two-frame delay and dead-audio controls reject. No subjective hearing or pop-free claim.</p>
<h2>Why the scheduling experiment is not usable</h2>
<p>The first helper used an unmapped bank00 address and failed. That variant is retained.
Two mapped variants—including one preserving incoming A/P—then failed settings loading:
2940-frame captures stop at the wait-settings deadline rather than completing the pause scenario.
The preserved variant's failure repeats exactly with observation enabled. Its11 inspected NMI helper
calls all take the no-sound path and preserve A and the return stack. This rules out newly executed
pause sound service as the cause in that window; the underlying boot timing dependency is unresolved.</p>
<div class="pair"><figure><img src="working-settings.png"><figcaption>Working3583: settings loaded</figcaption></figure>
<figure><img src="rejected-settings.png"><figcaption>Rejected3621: black screen at settings deadline</figcaption></figure></div>
<h2>Working build: status is still correct</h2><div class="pair"><figure><img src="nes-status.png"><figcaption>NES reference</figcaption></figure>
<figure><img src="working-status.png"><figcaption>Working3583</figcaption></figure></div>
<p>Next: trace the boot publication dependency before moving audio across it, then repeat the pause
onset test, full sound-event cadence, graphics publication and physical audio checks. Speed and scrolling
remain part of the active goal; this investigation does not certify their completion.</p>
<p><a href="report.json">Exact events, rejected trials and source bindings</a></p>'''
    (out/'index.html').write_text(body)
    for p,h in sources.items():
        if sha(Path(p))!=h:raise ValueError('Source changed during review')
    report=dict(summary=summary,sources=sources,artifacts={p.name:sha(p) for p in out.iterdir()},
        fix_verified=False,release_ready=False,physical_audio_verified=False,
        scope=__doc__+' A complete diagnostic result is not a successful game fix.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),fix_verified=False,source_bindings=len(sources))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    review(**vars(p.parse_args()))
