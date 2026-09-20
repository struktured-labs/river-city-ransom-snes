"""Qualify the phase80 trial's observed route without claiming original-speed or pop-free acceptance."""
import argparse
import html
import json
from pathlib import Path
import shutil
import time
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha, verify_capture
from tools.review_row_publication import audio_and_cadence

ROOT=Path('build/overflow-3526')
GAME=Path('build/audio-phase-bank-game-3665')


def review(out):
    if out.exists():raise ValueError('Fresh report required')
    started=time.monotonic();sources={}
    def proof(p):
        r=bound_report(p);sources.update(r['sources']);sources[str(p)]=sha(p);return r
    def bind(p):sources[str(p)]=sha(p)
    def capture(folder):
        r,rows=verify_capture(folder)
        for name in ('capture.json','timeline.json','audio.wav'):bind(folder/name)
        if not r['capture_complete'] or any(x['fault'] or x['input_requested']!=x['input_delivered'] for x in rows):
            raise ValueError('Incomplete/faulty/input-mismatched capture')
        return r,rows
    meta=json.loads((GAME/'manifest.json').read_text())
    if meta['rom_sha256']!=sha(GAME/'native-cpu.sfc'):raise ValueError('Changed candidate')
    for key in ('experimental_audio_phase','experimental_audio_phase_fast','experimental_audio_phase_bank'):
        for p,h in meta[key]['sources'].items():
            if sha(Path(p))!=h:raise ValueError('Changed implementation: '+p)
            sources[p]=h
    for p in (GAME/'manifest.json',GAME/'native-cpu.sfc'):bind(p)
    normal=ROOT/'audio-phase-sweep-3672'
    receipt,rows=capture(normal)
    audio,bindings=audio_and_cadence(GAME,normal,ROOT/'audio-phase-audio-main-3674')
    sources.update(bindings);bind(ROOT/'audio-phase-audio-main-3674/startup-game.json')
    dma=proof(ROOT/'audio-phase-dma-audit-3678/report.json')
    renderer=proof(ROOT/'audio-phase-render-audit-3679/report.json')
    observer=proof(ROOT/'audio-phase-render-observed-3677/renderer-observer.json')
    r0,t0=capture(ROOT/'audio-phase-render-normal-3675')
    r1,t1=capture(ROOT/'audio-phase-render-observed-3677')
    if r0['core_sha256']!=r1['core_sha256'] or t0!=t1 or r0['audio_sha256']!=r1['audio_sha256']:
        raise ValueError('Renderer not same-core neutral')
    pause=proof(Path('build/audio-phase-review-3670/report.json'))
    onset=proof(Path('build/audio-phase-onset-3667/report.json'))
    statuspath=Path('build/audio-phase-status-3669/report.json');status=json.loads(statuspath.read_text());bind(statuspath)
    for c in status['captures'].values():
        folder=Path(c['path']);capture(folder)
        if sha(folder/'capture.json')!=c['sha256']:raise ValueError('Changed status evidence')
    terminal=normal/(rows[-1]['phase']+'.ram');bind(terminal);ram=terminal.read_bytes()
    accounting=dict(scheduled=int.from_bytes(ram[0x1caa:0x1cac],'little'),
        served=int.from_bytes(ram[0x1cac:0x1cae],'little'),
        fallback=int.from_bytes(ram[0x1cae:0x1cb0],'little'),pending=ram[0x1ca3])
    checks=dict(full_route=receipt['capture_complete'],renderer=renderer['passed'],dma=dma['passed'],
        sound_startup=audio['audio']['passed'],stable_game_cadence=audio['cadence']['passed'],
        pause_onset=onset['passed'],pause_commands=pause['source_commands_equal'],status=status['passed'],
        terminal_accounting=accounting['scheduled']==accounting['served']>0 and accounting['pending']==0)
    summary=dict(checks=checks,frames=len(rows),rom_sha256=receipt['rom_sha256'],
        renderer_eligible=renderer['eligible_frames'],renderer_failures={k:len(renderer[k]) for k in
            ('coverage_failures','splits','stale_camera_failures')},
        dma_transfers=dma['dma_transfers'],dma_populations=dma['populations'],
        latest_visible_dma_end=dma['latest_visible_end'],accounting=accounting,
        audio={k:audio['audio'][k] for k in ('passed','packets','restarts','samples','peak','max_adjacent_step','clipped')},
        cadence={k:{q:v[q] for q in ('intervals','frame_histogram','busy_intervals','passed')}
                 for k,v in audio['cadence']['rooms'].items()},
        request_wait_ms=pause['request_wait_ms'],previous_wait_ms=pause['previous_wait_ms'])
    out.mkdir(parents=True)
    source=normal/'audio.wav';shutil.copyfile(source,out/'native-audio.wav')
    if sha(source)!=sha(out/'native-audio.wav'):raise ValueError('Changed native PCM')
    body='<!doctype html><meta charset="utf-8"><title>Audio phase route qualification</title>'
    body+='<style>body{background:#101820;color:#eef;font:18px system-ui;max-width:1050px;margin:30px auto}a{color:cyan}td{padding:9px;border-bottom:1px solid #456}audio{width:100%}</style>'
    body+='<h1>Experimental audio phase: full-route tradeoff checks</h1>'
    body+='<p>Candidate3665, not deployed. Fresh9090-frame park sweep with exact same-core observer neutrality. These scoped checks do not establish original-NES speed, all scrolling behavior or pop-free audio.</p><table>'
    values=[('Pause source-command wait',f'{pause["previous_wait_ms"]:.3f} → {pause["request_wait_ms"]:.3f}ms; NES2.415ms'),
        ('Pause PCM onset','57 frames, matching NES; previous58'),
        ('Actual rendered scrolling',f'{renderer["eligible_frames"]} eligible frames; PASS={renderer["passed"]}; failures={summary["renderer_failures"]}'),
        ('General DMA',f'{dma["dma_transfers"]} envelopes; PASS={dma["passed"]}; latest visible end line{dma["latest_visible_end"]}'),
        ('Sound startup',f'{audio["audio"]["packets"]} packets, {audio["audio"]["restarts"]} restart checks; PASS={audio["audio"]["passed"]}'),
        ('Stable room game cadence',json.dumps(summary['cadence'])),
        ('Terminal scheduler accounting',json.dumps(accounting))]
    body+=''.join('<tr><td>'+html.escape(k)+'</td><td>'+html.escape(v)+'</td></tr>' for k,v in values)+'</table>'
    body+='<h2>Untouched native full-route audio</h2><audio controls preload="none" src="native-audio.wav"></audio>'
    body+='<p>32040Hz stereo PCM, native gain/sample order. No clipping or correct startup does not prove absence of popping. Balanced terminal counters do not prove every tick met its deadline. Busy/nonstable/censored loop records remain in JSON.</p>'
    body+='<p>Remaining: actual IRQ context/stack preservation, pause fallback timing, sprite/CHR source publication, matched-original workload speed, expanded encounters and physical audio. No release or hardware claim.</p>'
    body+='<p><a href="report.json">Full records and hash bindings</a> · <a href="../audio-phase-review-3670/">Pause clocks and native comparison clips</a></p>'
    (out/'index.html').write_text(body)
    for p in (Path(__file__),Path('tools/review_row_publication.py'),Path('tools/audit_ordinary_route_timing.py'),
              Path('tools/audit_postpublish_keyon.py'),Path('tools/audit_pulse_onset.py'),
              Path('tools/audit_startup_pitch_game.py'),Path('tools/review_restart_volume.py')):bind(p)
    for p,h in sources.items():
        if sha(Path(p))!=h:raise ValueError('Changed source: '+p)
    report=dict(passed=all(checks.values()),summary=summary,checks=checks,audio_and_cadence=audio,
        sources=sources,artifacts={p.name:sha(p) for p in out.iterdir()},seconds=time.monotonic()-started,
        release_ready=False,physical_verified=False,pop_free_verified=False,scope=__doc__)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'],summary=summary,seconds=report['seconds'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    review(**vars(p.parse_args()))
