"""Verify the empty-tail transition fix and its isolated offline qualification."""
import argparse
import csv
import html
import json
from pathlib import Path
import shutil
import time
from tools.audit_main_display_latency import bound_report
from tools.audit_park_instructions import parse
from tools.benchmark_report import sha,verify_capture
from tools.consumer_empty_tail import assemble,patch
from tools.review_exact_row_scan import compare,load as row_load
from tools.review_row_publication import audio_and_cadence

ROOT=Path('build/overflow-3526')
GAME=Path('build/empty-tail-game-3631')


def review(out):
    started=time.monotonic()
    if out.exists():raise ValueError('Fresh output required')
    sources={}
    def bind(p):sources[str(p)]=sha(p)
    def proof(p):
        r=bound_report(p);sources.update(r['sources']);bind(p);return r
    def capture(folder):
        r,t=verify_capture(folder)
        for name in ('capture.json','timeline.json','audio.wav'):bind(folder/name)
        return r,t
    image=(GAME/'native-cpu.sfc').read_bytes()
    parent=Path('build/consumer-mixed-game-3583/native-cpu.sfc')
    if patch(parent.read_bytes(),assemble())!=image:raise ValueError('Changed isolated candidate')
    for folder in (GAME,Path('build/empty-tail-paused-game-3629')):
        m=json.loads((folder/'manifest.json').read_text())
        if sha(folder/'native-cpu.sfc')!=m['rom_sha256']:raise ValueError('Changed trial')
        for p,h in m['experimental_consumer_empty_tail']['sources'].items():
            if sha(Path(p))!=h:raise ValueError('Changed implementation source')
            sources[p]=h
        bind(folder/'manifest.json');bind(folder/'native-cpu.sfc')
    before,old=capture(ROOT/'paused-audio-preserved-status-3622')
    obs_before,old_obs=capture(ROOT/'transition-rejected-observed-3628')
    after,new=capture(ROOT/'empty-tail-paused-status-3630')
    obs_after,new_obs=capture(ROOT/'empty-tail-transition-observed-3642')
    proof(ROOT/'empty-tail-transition-observed-3642/pause-observer.json')
    for a,b,x,y in ((before,obs_before,old,old_obs),(after,obs_after,new,new_obs)):
        if x!=y or any(a[k]!=b[k] for k in
                ('core_sha256','rom_sha256','frames','audio_sha256','scenario_sha256','capture_complete')):
            raise ValueError('Root-cause observer changed execution')
    if before['capture_complete'] or not after['capture_complete']:
        raise ValueError('Known-broken boot did not fail, or repair did not complete')
    stages={}
    for name,file in [('before','transition-rejected-observed-3628.csv'),
                      ('after','empty-tail-transition-observed-3642-instructions.csv')]:
        path=ROOT/file;bind(path)
        with path.open() as f:ins=parse(csv.reader(f),580,582)
        def one(pc):
            rs=[r for r in ins if r['frame']==580 and r['pc']==pc]
            if len(rs)!=1:raise ValueError('Ambiguous stage')
            return rs[0]
        start=next(r for r in ins if r['frame']==580 and r['pc']==0xc0839e)
        finish=one(0xc0844f);admission=one(0xc086c8)
        stages[name]=dict(start=start,finish=finish,admission=admission,
            scan_master_clocks=finish['clock']-start['clock'],
            admitted=any(r['pc']==0xc08460 and r['frame']==580 for r in ins))
    a,b=stages['before'],stages['after']
    if (any(a['start'][k]!=b['start'][k] for k in ('frame','clock','a','x','y','s'))
            or a['admitted'] or not b['admitted'] or b['scan_master_clocks']>=a['scan_master_clocks']):
        raise ValueError('No exact-entry scan/admission improvement')
    windows={}
    for name,control,folder in [('health','row-resume-control-3449','empty-tail-health-3638'),
                               ('dialogue','row-resume-dialogue-control-3451','empty-tail-dialogue-3639')]:
        windows[name]=compare(Path('build')/control,ROOT/folder)
        for p in (Path('build')/control,ROOT/folder):
            report,_,_=row_load(p);sources.update(report['sources']);bind(p/'report.json')
    health=next(p['after'] for p in windows['health']['publication']['2']['comparisons'] if p['identity'][1]==9)
    dialogue=[p['after'] for p in windows['dialogue']['publication']['25']['comparisons']]
    normal=ROOT/'empty-tail-full-3640';receipt,rows=capture(normal)
    audio,bindings=audio_and_cadence(GAME,normal,ROOT/'empty-tail-audio-3643');sources.update(bindings)
    dma=proof(ROOT/'empty-tail-dma-audit-3648/report.json')
    renderer=proof(ROOT/'empty-tail-render-audit-3646/report.json')
    renderer_obs=proof(ROOT/'empty-tail-render-observed-3644/renderer-observer.json')
    rn,_=capture(ROOT/'empty-tail-render-normal-3641')
    ro,_=capture(ROOT/'empty-tail-render-observed-3644')
    if rn['core_sha256']!=ro['core_sha256']:raise ValueError('Need same-core renderer control')
    status=json.loads(Path('build/empty-tail-status-audit-3636/report.json').read_text())
    bind(Path('build/empty-tail-status-audit-3636/report.json'))
    for c in status['captures'].values():
        if sha(Path(c['path'])/'capture.json')!=c['sha256']:raise ValueError('Changed status capture')
    pause=proof(Path('build/empty-tail-audio-3635/report.json'))
    checks=dict(broken_boot_rejected=not before['capture_complete'],fixed_boot=after['capture_complete'],
        exact_entry_scan_faster=b['scan_master_clocks']<a['scan_master_clocks'],
        final_admission_recovered=b['admitted'],full_route=receipt['capture_complete'],
        exact_gameplay_guards=all(all(w['gates'].values()) for w in windows.values()),
        health_preserved=health['status']=='published' and health['vram_latency']<=3,
        dialogue_preserved=len(dialogue)==11 and all(d['status']=='published' and d['vram_latency']<=3 for d in dialogue),
        renderer=renderer['passed'],dma=dma['passed'],status=status['passed'],
        audio_startup=audio['audio']['passed'],cadence=audio['cadence']['passed'])
    summary=dict(checks=checks,rom_sha256=sha(GAME/'native-cpu.sfc'),
        root_scan_master_clocks=[a['scan_master_clocks'],b['scan_master_clocks']],
        admission_lines=[a['admission']['line'],b['admission']['line']],
        source_health_latency=health['vram_latency'],dialogue_latencies=[p['vram_latency'] for p in dialogue],
        full_frames=receipt['frames'],dma_transfers=dma['dma_transfers'],latest_visible_dma_end=dma['latest_visible_end'],
        renderer_eligible=renderer['eligible_frames'],
        audio={k:audio['audio'][k] for k in ('passed','packets','restarts','samples','peak','max_adjacent_step','clipped')},
        cadence={k:{q:v[q] for q in ('intervals','frame_histogram','busy_intervals','passed')}
                 for k,v in audio['cadence']['rooms'].items()},
        pause_onset=dict(nes=pause['nes']['frame_offset'],snes=pause['snes']['frame_offset'],passed=pause['passed']))
    out.mkdir(parents=True)
    media=[(ROOT/'paused-audio-preserved-status-3622/frames/frame-00582.png','before.png'),
           (ROOT/'empty-tail-paused-status-3630/frames/frame-00582.png','after.png'),
           (normal/'audio.wav','native-audio.wav')]
    for source,name in media:
        bind(source);shutil.copyfile(source,out/name)
        if sha(source)!=sha(out/name):raise ValueError('Changed exported media')
    body='''<!doctype html><meta charset="utf-8"><title>Empty queue transition fix</title>
<style>body{background:#101821;color:#eef;font:17px system-ui;max-width:1050px;margin:28px auto}
a{color:#9df}.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}img{width:100%;image-rendering:pixelated}
figure{margin:4px}td{padding:8px;border-bottom:1px solid #456}audio{width:100%}</style>
<h1>Fixed the reproduced settings-transition stall</h1>
<p>Experimental3631 shortens empty row-queue misses. No DMA deadline, game logic, original graphics
or sound engine changes. No deployment or release-ready claim.</p>
<p>The audio experiment exposed an endlessly rejected display handoff: an empty queue scan plus readiness
check reached the unchanged254-line cutoff. The shortened scan admits that same final update.
The extra pause-audio scheduling experiment is not retained in3631: it did not fix the delayed sound.</p>
<div class="pair"><figure><img src="before.png"><figcaption>Broken3621: frame582</figcaption></figure>
<figure><img src="after.png"><figcaption>Same audio experiment + queue fix3629: frame582</figcaption></figure></div>
<h2>Measured improvement and regression checks</h2><table>'''
    entries=[('Same-entry empty scan',f"{a['scan_master_clocks']} → {b['scan_master_clocks']} master clocks"),
        ('Final admission',f"Line{a['admission']['line']} rejected → line{b['admission']['line']} admitted; cutoff unchanged"),
        ('Known-broken replay','2940-frame settings timeout → complete2536-frame pause/status route'),
        ('Isolated3631 full route',str(receipt['frames'])+' frames'),
        ('Scrolling renderer',str(renderer['eligible_frames'])+' eligible frames; pass='+str(renderer['passed'])),
        ('General DMA',str(dma['dma_transfers'])+' envelopes; pass='+str(dma['passed'])),
        ('Health / dialogue','3 frames / all11 glyphs in2–3; exact-state gameplay guards pass'),
        ('Audio startup',str(audio['audio']['packets'])+' packets, '+str(audio['audio']['restarts'])+' restarts; pass='+str(audio['audio']['passed'])),
        ('Pause sound delay','Still58 vs NES57; FAIL retained, no claimed fix')]
    body+=''.join('<tr><td>'+html.escape(k)+'</td><td>'+html.escape(v)+'</td></tr>' for k,v in entries)+'</table>'
    body+='''<h2>Unmodified native full-route audio</h2><audio controls preload="none" src="native-audio.wav"></audio>
<p>32040Hz stereo PCM, native gain and sample order. Clean startup and no clipping do not establish
pop-free sound; no subjective hearing claim.</p><p>Observers preserve full video/input/state timelines
and native PCM against their own same-core controls. Cross-cartridge picture, state and audio differences
are retained. The small same-entry timing recovery proves this reproduced stall, not all possible NMI
arrival phases. Matched original-NES gameplay speed, expanded graphics/controller routes, current physical
audio and full release qualification remain open.</p><p><a href="report.json">Exact events, all differences and source bindings</a></p>'''
    (out/'index.html').write_text(body)
    for p in (Path(__file__),Path('tools/review_exact_row_scan.py'),Path('tools/review_row_publication.py'),
              Path('tools/audit_park_instructions.py'),Path('tests/test_consumer_empty_tail.py'),parent):bind(p)
    for p,h in sources.items():
        if sha(Path(p))!=h:raise ValueError('Changed review source: '+p)
    result=dict(summary=summary,checks=checks,passed=all(checks.values()),release_ready=False,
        physical_verified=False,pop_free_verified=False,stages=stages,exact_windows=windows,
        audio_and_cadence=audio,pause=pause,sources=sources,
        artifacts={p.name:sha(p) for p in out.iterdir()},seconds=time.monotonic()-started,
        scope=__doc__+' Isolated queue improvement, not completion of speed/scrolling/audio goal.')
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(summary=summary,passed=result['passed'],seconds=result['seconds'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    review(**vars(p.parse_args()))
