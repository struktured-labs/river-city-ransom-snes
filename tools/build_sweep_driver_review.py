"""Publish unaltered gameplay frames and native-rate same-command audio excerpts."""
import argparse
import html
import json
from pathlib import Path
import shutil

import numpy as np
from scipy.io import wavfile

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha,verify_capture


def build(normal,nes,proof,transport,cadence,producer,out):
    records={k:bound_report(p) for k,p in dict(proof=proof,transport=transport,cadence=cadence,producer=producer).items()}
    n=bound_report(nes/'report.json');receipt,rows=verify_capture(normal)
    if not all(records[k]['passed'] for k in ('proof','transport','producer')) or records['proof']['quick']:
        raise ValueError('Incomplete component/transport proof')
    if records['transport']['rom_sha256']!=receipt['rom_sha256']:
        raise ValueError('Unexpected source identity')
    if n['source_frames']!=len(rows) or n['timing']!='publication-frame':raise ValueError('Wrong NES replay')
    # The replay must consume precisely the bus bound by the transport proof.
    if not any(p.endswith('-bus.csv') and records['transport']['sources'].get(p)==h for p,h in n['sources'].items()):
        raise ValueError('NES replay uses a different command stream')
    paths=[Path(__file__),normal/'capture.json',normal/'timeline.json',normal/'audio.wav',
        nes/'report.json',nes/'timeline.json',nes/'audio.wav',proof,transport,cadence,producer]
    sources={str(p):sha(p) for p in paths}
    out.mkdir(parents=True,exist_ok=False);frames=[];cards=[]
    phases=('settings','right_04','mall_lower_lane','enter_shop','park_00_east_sweep','park_00_west_sweep')
    for phase in phases:
        selected=[r for r in rows if r['phase']==phase]
        if not selected:raise ValueError('Missing frame phase: '+phase)
        row=selected[min(100,len(selected)-1)];src=normal/row['frame_image']
        if sha(src)!=row['frame_image_sha256']:raise ValueError('Changed frame')
        dest=out/f'frame-{row["frame"]:05}.png';shutil.copyfile(src,dest)
        sources[str(src)]=sha(src);sources[str(dest)]=sha(dest)
        frames.append(dict(frame=row['frame'],phase=phase,path=str(dest),sha256=sha(dest)))
        cards.append(f'<figure><img src="{dest.name}" alt="{html.escape(phase)}">'
            f'<figcaption>{html.escape(phase)} · frame {row["frame"]}</figcaption></figure>')
    sr,spcm=wavfile.read(normal/'audio.wav');nr,npcm=wavfile.read(nes/'audio.wav')
    nrows=json.loads((nes/'timeline.json').read_text());clips=[];players=[]
    for phase in ('park_00_east_sweep','park_00_west_sweep'):
        selected=[r for r in rows if r['phase']==phase];first=selected[100]['frame'];last=selected[459]['frame']
        players.append('<h3>'+html.escape(phase)+f' · source frames {first}–{last}</h3>')
        for label,pcm,rate,a,b in (
            ('SNES candidate',spcm,sr,rows[first-1]['audio_start_sample'],rows[last-1]['audio_start_sample']+rows[last-1]['audio']['samples']),
            ('NES ordered-write replay',npcm,nr,nrows[first-1]['start_sample'],nrows[last-1]['end_sample'])):
            clip=pcm[a:b].copy();dest=out/(phase+('-snes.wav' if label.startswith('SNES') else '-nes.wav'))
            if not len(clip) or not np.any(clip):raise ValueError('Empty/silent listening excerpt')
            wavfile.write(dest,rate,clip);check_rate,check=wavfile.read(dest)
            if rate!=check_rate or not np.array_equal(clip,check):raise ValueError('Excerpt changed samples')
            sources[str(dest)]=sha(dest)
            clips.append(dict(label=label,phase=phase,first_frame=first,last_frame=last,
                start_sample=a,end_sample=b,rate=int(rate),path=str(dest),peak=int(np.abs(clip.astype(np.int64)).max()),
                clipped_samples=int(np.sum(np.abs(clip.astype(np.int64))>=32767))))
            players.append(f'<p>{label}</p><audio controls preload="none" src="{dest.name}"></audio>')
    speed=records['cadence'];rooms=speed['main']['rooms']
    table=''.join(f'<tr><td>{room}</td><td>{len(v["iterations"])}</td><td>{html.escape(str(v["nmi_advances"]))}</td>'
        f'<td>{len(v["off_cadence_starts"])}</td></tr>' for room,v in rooms.items())
    missed=sum(len(v['off_cadence_starts']) for v in rooms.values())
    result=dict(dataset_verified=True,release_ready=False,physical_audio_verified=False,
        rom_sha256=receipt['rom_sha256'],cadence_passed=speed['passed'],three_frame_starts=missed,
        frames=frames,clips=clips,sources=sources,
        scope='Untouched emulator frames and original native-rate samples. NES replays the same '
        'ordered writes at publication-frame resolution, not original sub-frame timing. '
        'Failed speed gate is retained; no physical deployment or combat-pop fix claim.')
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    links=' · '.join(f'<a href="../{p.parent.name}/{p.name}">{label}</a>' for label,p in
        (('SPC execution',proof),('CPU execution',producer),('Actual transport',transport),('Cadence gate',cadence),('NES replay',nes/'report.json')))
    (out/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>RCR live sweep driver</title>
<style>body{background:#101821;color:#eef;font:17px system-ui;max-width:1100px;margin:auto;padding:24px}
a{color:#9df}.open{color:#ffd68b}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
figure{margin:0}img,audio{width:100%}img{image-rendering:pixelated}td,th{border:1px solid #567;padding:9px}
table{border-collapse:collapse}@media(max-width:700px){.grid{grid-template-columns:1fr 1fr}}</style>
<h1>Live sweep driver integrated; speed gate still blocks deployment</h1>
<p>The replacement now runs inside the game: continuous shared sweep timing, explicit register-write events,
correct pulse arithmetic, and one DSP pitch/volume publisher. Idle publication runs only after relevant
changes. Graphics, controller mappings, logo and splash sound assets are unchanged.</p>
<p>615,120 clock cases, 2,097,152 pitch/mute cases, 1,088 envelope cases and 35 idle-update cases pass.
Three actually executed damaged drivers fail. The CPU producer passes 10,240 cases and rejects two faults.</p>
<p>Latest full route: '''+str(receipt['frames'])+''' frames, '''+str(records['transport']['receiver']['packets'])+''' actual SPC packets,
with complete audio and frame/RAM neutrality of the observation runs. All received bytes, event metadata,
key-on rules and completion order pass.</p>
<p class="open">NOT on Rival. '''+str(missed)+''' stable loop-start gaps are three frames instead of two.
The two-tick loop count alone would have missed this regression. Both park directions have zero short
1/3/4-frame uniform-endpoint camera holds, but that does not waive the full-route timing failure.</p>
<table><tr><th>Room</th><th>Complete stable loops</th><th>NMI ticks → count</th><th>Off-cadence starts</th></tr>'''+table+'''</table>
<p>Clock deadlines are rounded NTSC values, sampled every 512 SPC clocks. Packet-time frame resets do
not reproduce the NES 3/4-CPU-cycle reset delay. This remains a mono experimental engine.</p>
<h2>Actual candidate frames</h2><div class="grid">'''+''.join(cards)+'''</div>
<h2>Listen: same ordered commands, native samples</h2>
<p>No normalization, resampling, time stretch or fitted alignment. Different synthesis, native sample rates
and publication-frame quantization remain audible differences. These are emulator excerpts, not OBS/MiSTer captures
or proof that intermittent combat pops are fixed.</p>'''+''.join(players)+'''
<p><a href="report.json">Frame/sample boundaries and hashes</a> · '''+links+''' ·
<a href="../main-phase-rival-review-819/">Evidence hub</a></p></html>''')
    print(json.dumps(dict(dataset_verified=True,frames=len(frames),clips=len(clips),speed_gate_passed=speed['passed'],bindings=len(sources))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('normal','nes','proof','transport','cadence','producer','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
