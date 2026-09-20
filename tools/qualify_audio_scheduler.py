"""Parameterized scoped scheduler qualification; no inherited cartridge passes."""
import argparse
import html
import json
from pathlib import Path
import shutil
import time
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha,verify_capture
from tools.review_row_publication import audio_and_cadence


def qualify(candidate,normal,audio_observed,render_normal,render_observed,render_audit,
            dma_audit,state_audit,onset,status,out):
    if out.exists():raise ValueError('Fresh output required')
    started=time.monotonic();sources={}
    def bind(p):sources[str(p)]=sha(p)
    def proof(p):
        r=bound_report(p);sources.update(r['sources']);bind(p);return r
    def capture(folder):
        r,rows=verify_capture(folder)
        if not r['capture_complete'] or any(x['fault'] or x['input_requested']!=x['input_delivered'] for x in rows):
            raise ValueError('Incomplete/faulty/input-mismatched capture')
        for name in ('capture.json','timeline.json','audio.wav'):bind(folder/name)
        return r,rows
    digest=sha(candidate/'native-cpu.sfc');meta=json.loads((candidate/'manifest.json').read_text())
    if digest!=meta['rom_sha256']:raise ValueError('Changed candidate')
    for key,value in meta.items():
        if not key.startswith('experimental_audio_phase'):continue
        for p,h in value['sources'].items():
            if sha(Path(p))!=h:raise ValueError('Changed scheduler dependency: '+p)
            sources[p]=h
    bind(candidate/'native-cpu.sfc');bind(candidate/'manifest.json')
    receipt,rows=capture(normal)
    if receipt['rom_sha256']!=digest:raise ValueError('Different normal cartridge')
    audio,bindings=audio_and_cadence(candidate,normal,audio_observed);sources.update(bindings)
    bind(audio_observed/'startup-game.json')
    renderer=proof(render_audit/'report.json');dma=proof(dma_audit/'report.json')
    for folder in (render_normal,render_observed):
        p=folder/'capture.json'
        if renderer['sources'].get(str(p))!=sha(p):raise ValueError('Renderer audit belongs to another replay')
    p=normal/'capture.json'
    if dma['sources'].get(str(p))!=sha(p):raise ValueError('DMA audit is not bound to current primary route')
    proof(render_observed/'renderer-observer.json')
    r0,t0=capture(render_normal);r1,t1=capture(render_observed)
    if t0!=t1 or any(r0[k]!=r1[k] for k in ('core_sha256','rom_sha256','audio_sha256')):
        raise ValueError('Changed renderer observation')
    if r0['rom_sha256']!=digest or dma['rom_sha256']!=digest:raise ValueError('Different graphics cartridge')
    state=proof(state_audit/'report.json');pause=proof(onset/'report.json')
    if pause['captures']['snes']['rom_sha256']!=digest:raise ValueError('Different onset cartridge')
    state_captures=[Path(p) for p in state['sources'] if p.endswith('/capture.json')]
    if not state_captures or any(json.loads(p.read_text())['rom_sha256']!=digest for p in state_captures):
        raise ValueError('Different context cartridge')
    s=json.loads((status/'report.json').read_text());bind(status/'report.json')
    for key,p in [('audit_sha256',Path('tools/check_status_regression.py')),
                  ('oracle_sha256',Path('tools/check_present_status.py'))]:
        if s[key]!=sha(p):raise ValueError('Changed status oracle')
        bind(p)
    if s['captures']['snes']['rom_sha256']!=digest:raise ValueError('Different status cartridge')
    for c in s['captures'].values():
        folder=Path(c['path']);capture(folder)
        if sha(folder/'capture.json')!=c['sha256']:raise ValueError('Changed status capture')
    terminal=normal/(rows[-1]['phase']+'.ram');bind(terminal);ram=terminal.read_bytes()
    accounting=dict(scheduled=int.from_bytes(ram[0x1caa:0x1cac],'little'),served=int.from_bytes(ram[0x1cac:0x1cae],'little'),
        pending=ram[0x1ca3],fallback=int.from_bytes(ram[0x1cae:0x1cb0],'little'))
    checks=dict(full_route=receipt['capture_complete'],renderer=renderer['passed'],dma=dma['passed'],
        sound_startup=audio['audio']['passed'],stable_cadence=audio['cadence']['passed'],
        pause_context=state['passed'],native_pause_onset=pause['passed'],status=s['passed'],
        terminal_accounting=accounting['scheduled']==accounting['served']>0 and accounting['pending']==0)
    summary=dict(rom_sha256=digest,frames=len(rows),checks=checks,accounting=accounting,
        renderer_eligible=renderer['eligible_frames'],dma_transfers=dma['dma_transfers'],
        latest_visible_dma_end=dma['latest_visible_end'],pause_irqs=state['count'],
        audio={k:audio['audio'][k] for k in ('passed','packets','restarts','samples','peak','max_adjacent_step','clipped')},
        cadence={k:{q:v[q] for q in ('intervals','frame_histogram','busy_intervals','passed')}
                 for k,v in audio['cadence']['rooms'].items()})
    out.mkdir(parents=True);shutil.copyfile(normal/'audio.wav',out/'native-audio.wav')
    if sha(normal/'audio.wav')!=sha(out/'native-audio.wav'):raise ValueError('Changed native audio')
    body='<!doctype html><meta charset="utf-8"><title>Guarded scheduler qualification</title>'
    body+='<style>body{background:#101820;color:#eef;font:18px system-ui;max-width:1050px;margin:30px auto}a{color:cyan}td{padding:10px;border-bottom:1px solid #456}audio{width:100%}pre{white-space:pre-wrap}</style>'
    body+='<h1>Guarded audio scheduler: current-cartridge route checks</h1><p>Experimental cartridge '+html.escape(str(candidate))+'. Not deployed or release qualified.</p><table>'
    entries=[('Full route',f'{len(rows)} frames'),('Scoped checks',json.dumps(checks)),
             ('Actual renderer',f'{renderer["eligible_frames"]} eligible frames; PASS={renderer["passed"]}'),
             ('General DMA',f'{dma["dma_transfers"]} envelopes; PASS={dma["passed"]}'),
             ('Audio startup',json.dumps(summary['audio'])),('Stable room cadence',json.dumps(summary['cadence'])),
             ('Terminal accounting',json.dumps(accounting))]
    body+=''.join('<tr><td>'+html.escape(k)+'</td><td>'+html.escape(v)+'</td></tr>' for k,v in entries)+'</table>'
    body+='<h2>Untouched native full-route PCM</h2><audio controls preload="none" src="native-audio.wav"></audio>'
    body+='<p>Same-core observation preserves full primary timelines and PCM. Correct startup, no clipping and balanced terminal counters do not establish pop-free sound or timely service of every tick. Busy/nonstable/censored records remain in JSON.</p>'
    body+='<p>Still required: direct-recovery context, expanded IRQ phases and encounters, sprite/CHR publication, matched NES workload speed and controlled physical audio. Pause IRQ-state coverage is not a full-route CPU-state audit.</p><p><a href="report.json">Complete records and bindings</a></p>'
    (out/'index.html').write_text(body)
    for p in (Path(__file__),Path('tools/review_row_publication.py'),Path('tools/audit_ordinary_route_timing.py'),
              Path('tools/audit_postpublish_keyon.py'),Path('tools/audit_startup_pitch_game.py'),
              Path('tools/audit_pulse_onset.py'),Path('tools/review_restart_volume.py')):bind(p)
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Changed qualification source')
    report=dict(passed=all(checks.values()),summary=summary,checks=checks,audio_and_cadence=audio,sources=sources,
        artifacts={p.name:sha(p) for p in out.iterdir()},seconds=time.monotonic()-started,
        release_ready=False,physical_verified=False,pop_free_verified=False,scope=__doc__)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'],summary=summary,seconds=report['seconds'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','normal','audio-observed','render-normal','render-observed','render-audit',
                 'dma-audit','state-audit','onset','status','out'):p.add_argument('--'+name,type=Path,required=True)
    qualify(**vars(p.parse_args()))
