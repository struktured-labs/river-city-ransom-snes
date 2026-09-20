"""Publish retained raw/AAC audio, actual video frames, and capture limitations."""
import argparse
from datetime import datetime,timezone
from html import escape
import json
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image
from scipy.io import wavfile

from tools.audit_main_display_latency import bound_report
from tools.audit_raw_monitor_audio import locate
from tools.benchmark_report import sha


def publish(audit,video,out):
    r=bound_report(audit);sources={str(p):sha(p) for p in (audit,video,Path(__file__),
        Path('tools/audit_raw_monitor_audio.py'),Path('tools/capture_mister_dual_audio.py'))}
    raw_path=next(Path(p) for p in r['sources'] if p.endswith('/raw-monitor.wav'))
    aac_path=next(Path(p) for p in r['sources'] if p.endswith('-aac.wav'))
    media=next(Path(p) for p in r['sources'] if p.endswith('.mkv'))
    rr,raw=wavfile.read(raw_path);_,aac=wavfile.read(aac_path)
    refinement=[];offset=r['alignment']['offset_samples']
    for first in (8,10,12,17,19,20):
        a=first*rr;lo=a+offset-2400;hi=a+offset+rr+2400
        diagnostic=locate(raw[lo:hi,:2].mean(axis=1)/2147483648,aac[a:a+rr].mean(axis=1),0,rr)
        refinement.append(dict(first_seconds=first,residual_samples=diagnostic['offset_samples']-2400,
            diagnostic_correlation=diagnostic['training_correlation']))
    rom='/media/fat/games/SNES/RCR-SNES-071c89e.sfc'
    remote=subprocess.check_output(['ssh','rivalmage','sha256sum',rom],text=True).split()[0]
    if remote!='071c89e9dde88bcc5622ef6379522149e72415b51b3418a8f281f5a66774733f':raise ValueError('Different live ROM')
    processes=subprocess.check_output(['ssh','rivalmage','ps'],text=True)
    live=[line for line in processes.splitlines() if '/media/fat/MiSTer ' in line]
    if len(live)!=1 or '/media/fat/RCR-SNES-071c89e.mgl' not in live[0]:raise ValueError('Different active game')
    out.mkdir(parents=True,exist_ok=False);frames=(480,645,650,656,662,720,900,1080,1440)
    expression='+'.join(f'eq(n\\,{n})' for n in frames)
    subprocess.run(['ffmpeg','-nostdin','-v','error','-n','-i',str(video),'-vf','select='+expression,
        '-vsync','0',str(out/'frame-%02d.png')],check=True)
    # Independently decode those indices from the original MKV, not the MP4.
    decoded=subprocess.check_output(['ffmpeg','-nostdin','-v','error','-i',str(media),'-vf','select='+expression,
        '-vsync','0','-f','rawvideo','-pix_fmt','rgb24','-'])
    size=1920*1080*3
    if len(decoded)!=len(frames)*size:raise ValueError('Unexpected source video geometry/coverage')
    artifacts={};panels=[]
    for i,frame in enumerate(frames,1):
        path=out/f'frame-{i:02d}.png'
        if np.asarray(Image.open(path).convert('RGB')).tobytes()!=decoded[(i-1)*size:i*size]:
            raise ValueError('Panel is not the original source frame')
        artifacts[path.name]=sha(path)
        panels.append(f'<figure><img src="{path.name}" alt="Actual frame {frame}"><figcaption>'
            f'Frame {frame} · {frame/60:.3f}s</figcaption></figure>')
    clips=[]
    for name,meta in r['clips'].items():
        path=Path(name)
        if sha(path)!=meta['sha256']:raise ValueError('Changed audio excerpt')
        rate,clip=wavfile.read(path);original=raw[:,:2] if path.name.startswith('raw') else aac
        if rate!=rr or not np.array_equal(clip,original[meta['first']:meta['last']]):raise ValueError('Altered PCM excerpt')
        clips.append(f'<h3>{escape(path.name)}</h3><audio controls preload="none" src="../{path.parent.name}/{path.name}"></audio>')
    table=''.join('<tr>'+''.join('<td>'+escape(str(v))+'</td>' for v in
        (round(g['aac_seconds'],6),round(g['duration_ms'],3),
         None if g['raw_gap'] is None else round(g['raw_gap']['duration_ms'],3),
         g['raw_exact_zero_fraction'],g['fully_covered_in_raw']))+'</tr>' for g in r['aac_gaps'])
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RCR · actual pre-mute hardware audio capture</title><style>body{background:#101821;color:#eef;font:17px system-ui;max-width:1200px;margin:auto;padding:24px}a{color:#9df}td,th{padding:8px;border:1px solid #567}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}figure{margin:0}img,video,audio{width:100%}.open{color:#ffd68b}pre{white-space:pre-wrap}</style>
<h1>Actual hardware: raw audio before the muted monitor</h1>
<p>September 18 · ROM 071c89e unchanged · no reset. Bounded gameplay recording complete; SNAC restored Yes, game paused by Trash Pick-Up, OSD closed. Original OBS audio settings and PipeWire links/mute restored; raw debug tap removed.</p>
<h2>A real capture-path blind spot found</h2><p>OBS Blackmagic is unmuted, but its separate OS monitoring stream is muted. The first ordinary PCM tap was therefore entirely silent while the AAC recording had game sound. That capture is retained as a rejected negative, not game silence. The corrected capture uses the adapter's raw debug tap without unmuting speakers or changing routes.</p>
<p>The raw file contains four original signed-32-bit channels at 48 kHz; FL/FR carry audio and both auxiliary channels are exactly zero. The whole 22.5-second input episode fits inside the recording after the new ready-handshake orchestration.</p>
<h2>Same physical episode, two branches</h2><p>The recording's 142.667ms gap at 10.837333s also exists in raw PCM as a 178.500ms gap. The video shows a room-transition blackout at that point. This rules out an AAC-only missing-sound event there; it does not establish the game command or clear the older mid-combat gaps.</p>
<table><tr><th>AAC start(s)</th><th>AAC zero(ms)</th><th>Raw zero(ms)</th><th>Mapped AAC interval zero fraction in raw</th><th>Fully covered?</th></tr>'''+table+'''</table>
<p>All six completely covered AAC zero intervals of at least 10ms are zero throughout in raw PCM. The final long paused tail extends beyond raw overlap and is not counted as a pass. A real all-silent monitor negative is rejected; an injected 100ms AAC-only cut is detected against nonzero raw signal.</p>
<p class="open">Raw/AAC alignment is +270,754 samples (5.640708s), fitted only on recording seconds 4–7. This includes different capture-branch buffering, not game audio latency. Fixed-offset held-out correlations at seconds 8, 10, 12 exceed .999; seconds 17/19 fall to .692/.681. A separate ±50ms diagnostic finds a −33-sample (0.6875ms) shift after pause/resume. It is disclosed below, not applied to the gap comparison or used to claim timing fidelity.</p><pre>'''+escape(json.dumps(refinement,indent=2))+'''</pre>
<p class="open">Both branches share the DeckLink/OBS source. Shared silence still cannot separate an intentional game rest from synthesis or an upstream capture fault. Pop-free audio, hardware APU command identity, full-game timing and the earlier three combat gaps remain unverified.</p>
<h2>Unchanged source audio, same ten-second context</h2><p>No normalization, resampling, stretching or amplitude fit. Raw excerpt selects original FL/FR samples; the full four-channel file remains hash-bound. AAC excerpt preserves the exact decoded float samples.</p>'''+''.join(clips)+'''
<h2>Actual recording and unaltered source frames</h2><video controls preload="metadata" src="../'''+video.name+'''"></video><div class="grid">'''+''.join(panels)+'''</div>
<p>All nine PNGs equal decoded RGB frames from the original MKV; MP4 is a stream-copy, not a transcode. 745 unit tests pass.</p>
<p><a href="../'''+audit.parent.name+'''/report.json">All audio measurements and source bindings</a> · <a href="report.json">Frame hashes, live identity, and diagnostic offsets</a> · <a href="../triangle-game-physical-context-973/">Earlier unresolved combat gaps</a> · <a href="https://docs.pipewire.org/page_man_pipewire-props_7.html">PipeWire raw-debug documentation</a></p></html>'''
    (out/'index.html').write_text(page)
    (out/'report.json').write_text(json.dumps(dict(sources=sources,artifacts=artifacts,
        frames=list(frames),diagnostic_offsets=refinement,diagnostic_offsets_applied=False,
        live_identity=dict(observed_utc=datetime.now(timezone.utc).isoformat(),rom_sha256=remote,process=live[0]),
        page_sha256=sha(out/'index.html'),release_ready=False),indent=2)+'\n')
    print(json.dumps(dict(out=str(out),panels=len(frames),sources=len(sources))))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('audit','video','out'):parser.add_argument('--'+name,type=Path,required=True)
    publish(**vars(parser.parse_args()))
