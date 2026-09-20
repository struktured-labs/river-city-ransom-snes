"""Local, asset-free diagnostic evidence page with native audio and real video."""
import argparse
from html import escape
import json
from pathlib import Path
import shutil
import subprocess

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha


def build(out):
    paths=[Path(p) for p in (
        'build/knockdown-packet-player-audit-1265/report.json',
        'build/knockdown-packet-player-video-1264/report.json',
        'build/packet-player-physical-audio-1279/report.json',
        'build/packet-player-physical-tail-audio-1288/report.json',
        'build/packet-player-physical-frames-1276/report.json',
        'build/packet-player-physical-tail-frames-1281/report.json',
        'build/knockdown-packet-player-hardware-1278/report.json')]
    reports=[bound_report(p) for p in paths]
    out.mkdir(parents=True,exist_ok=False)
    sections=[];sources={str(p):sha(p) for p in [Path(__file__),*paths]}
    for name,r,p in zip(('early','combat'),reports[2:4],paths[2:4]):
        if not r['silence_negative_detected']:raise ValueError('Failed audio sensitivity control')
        controls=[]
        for clip,meta in r['clips'].items():
            source=Path(clip)
            if sha(source)!=meta['sha256']:raise ValueError('Clip changed')
            target=out/(name+'-'+source.name);shutil.copyfile(source,target)
            controls.append(f'<label>{escape(source.stem)} ({meta["rate"]} Hz)<br>'
                            f'<audio controls preload="none" src="{target.name}"></audio></label>')
        held=', '.join(f'{x["correlation"]:.3f}' for x in r['held_out'])
        source=next(Path(k) for k in r['sources'] if k.endswith('.mkv'))
        target=out/(name+'.mp4')
        subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(source),'-map','0:v:0',
            '-map','0:a:0','-c','copy','-movflags','+faststart',str(target)],check=True)
        sections.append(f'<section><h2>{name.title()} replay</h2><p>Held-out RMS correlations: {held}. '
            f'Unexpected sustained silence: {len(r["unexpected_silence"])}. '
            f'<a href="{name}-report.json">Full report</a>.</p><div class="clips">'
            +''.join(controls)+f'</div><video controls preload="metadata" src="{target.name}"></video></section>')
        shutil.copyfile(p,out/(name+'-report.json'))
    figures=[]
    for source,label in ((Path('build/packet-replay-running-1267.png'),'Real Rival replay: binary source-frame marker'),
        (Path('build/packet-player-tail-corrupt-1290.png'),'Retained obstruction: MiSTer screenshot notification covers the marker'),
        (Path('build/packet-replay-final-snac-1285.png'),'After restoring the game: SNAC Yes'),
        (Path('build/packet-replay-final-handoff-1287.png'),'Final handoff: game restored, OSD closed')):
        target=out/source.name;shutil.copyfile(source,target);sources[str(source)]=sha(source)
        figures.append(f'<figure><a href="{target.name}"><img src="{target.name}" loading="lazy"></a>'
                       f'<figcaption>{escape(label)}</figcaption></figure>')
    for i,p in enumerate(paths):shutil.copyfile(p,out/f'proof-{i}.json')
    html='''<!doctype html><meta charset="utf-8"><title>RCR deterministic hardware audio replay</title>
<style>body{background:#10141b;color:#e3edf4;font:17px/1.5 system-ui;max-width:1180px;margin:30px auto;padding:20px}
a{color:#64e1eb}h1{font-size:30px}.clips,.frames{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:15px}
video,img{width:100%}figure{margin:0}figcaption{font-size:14px}section{border-top:1px solid #354354;margin-top:24px;padding-top:10px}
.warning{border-left:4px solid #ffb347;padding-left:16px}audio{max-width:100%}</style>
<h1>Same sound commands, emulator and Rival</h1>
<p>September 18, 2026 · Experimental diagnostic, not a new game release.</p>
<p>2,512 packets / 57,776 receiver bytes checked. Complete emulator waveform unchanged by the receiver observer.
Executed wrong-port and half-speed players rejected. All 2,906 emulator frame markers checked.</p>
<p class="warning">No sustained hardware-only silence detected by this test. This is <strong>not a pop-free or pitch-fidelity pass</strong>:
10 ms RMS bins cannot certify small clicks, and replay sends at VBlank rather than the game's original within-frame times.
Physical packet reception is not instrumented. Game speed and strict graphics publication remain open.</p>
<p>Two independent, overlapping hardware runs show frame ranges 1–1,603 and 1,361–2,906.
The later video retains 116 unreadable markers, including a visible MiSTer screenshot notification; no frames were erased or repaired.
OBS duplicates/skips are retained. The first attempted second recording was refused while OBS flushed; the game was restored safely.</p>
<p>Audio clips retain native samples and rates, without loudness normalization, pitch shifting or time warping.
Hardware raw and AAC share the DeckLink/OBS source. Each comparison uses one fixed RMS alignment and separate held-out windows.
An injected 100 ms capture-only dropout is caught in both comparisons.</p>
'''+''.join(sections)+'<section><h2>Unaltered capture frames</h2><div class="frames">'+''.join(figures)+'''</div></section>
<p>The previous playable ROM <code>0956bd97b78f</code> is restored on Rival; SNAC Yes, OSD closed, saved configuration unchanged.
Controller presets and the splash sound were not changed in this iteration.</p>
<p><a href="../retained-camera-review-1222/">Previous gameplay/camera evidence</a> · <a href="manifest.json">Evidence manifest</a></p>'''
    (out/'index.html').write_text(html)
    manifest=dict(sources=sources,artifacts={p.name:sha(p) for p in out.iterdir() if p.is_file()},
                  release_ready=False,pop_free_verified=False)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),artifacts=len(manifest['artifacts']))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    build(**vars(p.parse_args()))
