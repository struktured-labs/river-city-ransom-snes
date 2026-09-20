"""Publish scoped NMI/camera evidence and a recorded Rival trial, without retouching frames."""
import argparse
from html import escape
import json
from pathlib import Path
import shutil
import subprocess

import numpy as np
from scipy.io import wavfile

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha, verify_capture


def pause_pair(active, paused):
    if (active.ndim != 2 or active.shape[1] != 2 or not len(active) or
            paused.ndim != 2 or paused.shape[1] != 2 or not len(paused)):
        raise ValueError('Need nonempty stereo intervals')
    if not np.isfinite(active).all() or not np.isfinite(paused).all():
        raise ValueError('Nonfinite samples')
    ac = np.std(active.astype(np.float64), axis=0)
    if not np.all(ac > 0) or np.any(paused):
        raise ValueError('Dead gameplay channel or non-silent pause')
    return dict(active_channel_ac_rms=ac.tolist(), paused_nonzero_samples=0,
                active_frames=len(active), paused_frames=len(paused))


def publish(normal, nes, cadence, transport, nmi, camera, background, raw_audit,
            boot, coordinator, video, handoff, snac, out):
    reports = {k: bound_report(p) for k, p in dict(cadence=cadence, transport=transport,
        nmi=nmi, camera=camera, raw_audio=raw_audit, boot=boot,
        coordinator=coordinator, nes=nes/'report.json').items()}
    receipt, rows = verify_capture(normal)
    digest = receipt['rom_sha256']
    bg = json.loads(background.read_text())
    if not all(reports[k]['passed'] for k in ('cadence','transport','nmi','camera','nes')):
        raise ValueError('Component/route gate failed')
    if (reports['transport']['rom_sha256'] != digest or reports['boot']['rom_sha256'] != digest or
            bg['sources']['normal_snes']['capture_sha256'] != sha(normal/'capture.json')):
        raise ValueError('Different candidate')
    if not all(bg['gates'][k] for k in ('background_band_exact','expanded_background_playfield_exact',
                                       'nes_observer_neutral','snes_observer_neutral')):
        raise ValueError('Pixel/observer regression')
    if (reports['nes']['source_frames'] != len(rows) or reports['nes']['timing'] != 'publication-frame' or
            not any(p.endswith('-bus.csv') and reports['transport']['sources'].get(p) == h
                    for p,h in reports['nes']['sources'].items())):
        raise ValueError('Different NES command replay')
    raw = reports['raw_audio']
    if raw['sources'].get(str(coordinator)) != sha(coordinator):
        raise ValueError('Different physical episode')
    raw_path = next(Path(p) for p in raw['sources'] if p.endswith('/raw-monitor.wav'))
    aac_path = next(Path(p) for p in raw['sources'] if p.endswith('-aac.wav'))
    media = next(Path(p) for p in raw['sources'] if p.endswith('.mkv'))
    rr, raw_pcm = wavfile.read(raw_path)
    ar, aac_pcm = wavfile.read(aac_path)
    if rr != 48000 or ar != rr or raw_pcm.dtype != np.int32 or aac_pcm.dtype != np.float32:
        raise ValueError('Changed native formats')
    # Explicit local-file windows; NOT input-to-audio latency measurements.
    raw_pair = pause_pair(raw_pcm[9*rr:14*rr,:2], raw_pcm[29*rr:299*rr//10,:2])
    aac_pair = pause_pair(aac_pcm[4*rr:9*rr], aac_pcm[25*rr:29*rr])
    negatives = []
    click = np.zeros((100,2),np.int32)
    click[50,1] = 1
    for label, active, paused in (
        ('dead-gameplay', np.zeros((100,2), np.int32), np.zeros((100,2), np.int32)),
        ('paused-click', raw_pcm[9*rr:9*rr+100,:2], click)):
        try:
            pause_pair(active, paused)
        except ValueError:
            negatives.append(label)
        else:
            raise ValueError('Surviving pause control')
    out.mkdir(parents=True, exist_ok=False)
    source_paths = [Path(__file__), normal/'capture.json', normal/'timeline.json', normal/'audio.wav',
        nes/'report.json', nes/'timeline.json', nes/'audio.wav', cadence, transport, nmi, camera,
        background, raw_audit, boot, coordinator, video, handoff, snac, raw_path, aac_path, media]
    sources = {str(p): sha(p) for p in source_paths}
    artifacts = {}
    def copy(src, name):
        dest = out/name
        shutil.copyfile(src,dest)
        sources[str(src)] = sha(src)
        artifacts[name] = sha(dest)
        return name
    cards = []
    for phase in ('settings','right_04','mall_lower_lane','enter_shop','park_00_east_sweep','park_00_west_sweep'):
        selected = [r for r in rows if r['phase'] == phase]
        row = selected[min(100,len(selected)-1)]
        src = normal/row['frame_image']
        if sha(src) != row['frame_image_sha256']:
            raise ValueError('Changed source frame')
        name = copy(src, f'emulator-{row["frame"]:05}.png')
        cards.append(f'<figure><img src="{name}"><figcaption>{escape(phase)} · frame {row["frame"]}</figcaption></figure>')
    clips = []
    players = []
    sr, spcm = wavfile.read(normal/'audio.wav')
    nr, npcm = wavfile.read(nes/'audio.wav')
    nrows = json.loads((nes/'timeline.json').read_text())
    for phase in ('park_00_east_sweep','park_00_west_sweep'):
        selected = [r for r in rows if r['phase'] == phase]
        first,last = selected[100]['frame'], selected[459]['frame']
        for label, pcm, rate, a, b in (
            ('snes',spcm,sr,rows[first-1]['audio_start_sample'],rows[last-1]['audio_start_sample']+rows[last-1]['audio']['samples']),
            ('nes',npcm,nr,nrows[first-1]['start_sample'],nrows[last-1]['end_sample'])):
            name = phase+'-'+label+'.wav'
            clip = pcm[a:b]
            wavfile.write(out/name, rate, clip)
            check_rate, check = wavfile.read(out/name)
            if rate != check_rate or not np.array_equal(clip,check):
                raise ValueError('Changed audio samples')
            artifacts[name] = sha(out/name)
            clips.append(dict(name=name, rate=rate, first_sample=a, last_sample=b,
                              first_frame=first,last_frame=last))
            players.append(f'<p>{escape(phase)} · {label.upper()}</p><audio controls src="{name}"></audio>')
    for p, meta in raw['clips'].items():
        src = Path(p)
        if sha(src) != meta['sha256']:
            raise ValueError('Changed physical excerpt')
        copy(src,src.name)
    # Zero-based decoded frames around the longer combat/pause-resume gaps.
    indices = (180,480,642,648,656,1019,1026,1032,1560)
    expression = '+'.join(f'eq(n\\,{n})' for n in indices)
    subprocess.run(['ffmpeg','-nostdin','-v','error','-n','-i',str(media),'-vf','select='+expression,
        '-vsync','0',str(out/'physical-%02d.png')],check=True)
    panels = []
    for i, frame in enumerate(indices,1):
        name = f'physical-{i:02d}.png'
        artifacts[name] = sha(out/name)
        panels.append(f'<figure><img src="{name}"><figcaption>OBS frame {frame} (zero-based), {frame/60:.3f}s</figcaption></figure>')
    copy(handoff,'handoff.png'); copy(snac,'snac-restored.png')
    count = sum(len(v['iterations']) for v in reports['cadence']['main']['rooms'].values())
    summary = dict(rom_sha256=digest, stable_loops=count,
        background_samples=len(bg['comparisons']), strict_background_passed=bg['passed'],
        strict_late_observations=len(bg['late_publications']), raw_pause_pair=raw_pair,
        decoded_pause_pair=aac_pair, pause_controls_rejected=negatives,
        physical_alignment=raw['alignment'], physical_fixed_offset_checks=raw['held_out_fixed_offset'],
        release_ready=False, full_game_speed_verified=False, pop_free_verified=False,
        physical_scrolling_verified=False, clips=clips, physical_frames_zero_based=list(indices),
        artifacts=artifacts,sources=sources)
    (out/'report.json').write_text(json.dumps(summary,indent=2)+'\n')
    gaps = ''.join(f'<tr><td>{g["aac_seconds"]:.6f}</td><td>{g["duration_ms"]:.3f}</td><td>'+
        ('uncovered' if g['raw_gap'] is None else f'{g["raw_gap"]["duration_ms"]:.3f}')+'</td></tr>'
        for g in raw['aac_gaps'])
    links = ' · '.join(f'<a href="../{p.parent.name}/{p.name}">{label}</a>' for label,p in (
        ('NMI execution',nmi),('Camera execution',camera),('Cadence',cadence),('SPC delivery',transport),
        ('Background audit (strict FAIL)',background),('Raw audio audit',raw_audit),('Boot identity',boot)))
    (out/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>RCR: recovered NMI and Rival trial</title>
<style>body{background:#101821;color:#eef;font:17px system-ui;max-width:1200px;margin:auto;padding:24px}
a{color:#9df}.open{color:#ffd68b}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
figure{margin:0}img,video,audio{width:100%}img{image-rendering:pixelated}td,th{border:1px solid #567;padding:8px}
pre{white-space:pre-wrap}@media(max-width:700px){.grid{grid-template-columns:1fr}}</style>
<h1>Recovered interrupt + camera fix: now tested on Rival</h1>
<p>Build '''+digest[:12]+''' · September 18. The retained game-interrupt return now preserves a fresh
VBlank event. A late camera-only commit updates four WRAM bytes without starting graphics DMA.
Game art, controls and splash assets are unchanged.</p>
<p>280 executed interrupt cases, all 256 stack positions, 24 old-code controls and three broken variants.
40 complete-publisher beam/guard cases and eight broken variants. '''+str(count)+''' stable loops across
four rooms all take two ticks, with no off-cadence starts. 8,404 SPC packets and 5,613 sweep-write events pass.
All '''+str(len(bg['comparisons']))+''' matched background samples are pixel-exact.</p>
<p class="open">Strict same-frame graphics publication still FAILS ('''+str(len(bg['late_publications']))+'''
observations retained). This is not a full-game original-speed or pop-free release certification.</p>
<h2>Hardware trial and handoff</h2><p>The recorder was ready before boot and before controlled gameplay.
Both owned 30-second recordings stopped; the raw tap was removed and original routing restored.
SNAC is back to Yes; Rival is paused outside Cross-Town High School. Saved configuration unchanged;
previous ROM preserved. USB requests were visibly consumed; physical SNAC buttons were not tested.</p>
<div class="grid"><figure><img src="handoff.png"><figcaption>Actual handoff</figcaption></figure>
<figure><img src="snac-restored.png"><figcaption>Actual SNAC restoration</figcaption></figure></div>
<h2>Real sound: raw PCM alongside OBS</h2><p>Raw native 48 kHz signed-32 FL/FR samples and exact decoded
AAC float samples; no gain normalization or resampling. Paused raw seconds 29–29.9 and AAC seconds 25–29
are exactly zero, with active stereo gameplay in each source. Dead-gameplay and paused-click controls fail.</p>
<p class="open">AAC gaps around 10.795s and 17.088s have corresponding raw gaps of about 157ms and 154ms.
The first shows Alex knocked down on the street; the second is near pause/resume, with the menu still
partly visible. Neither has hardware command-level attribution. No claim that the sweep replacement
fixes all sputtering. The fixed
raw/AAC alignment has only 0.955 training correlation and 0.639–0.787 held-out correlations: it is a
capture-branch diagnostic, not sample-exact game-event attribution or a game-latency measurement.</p>
<p>This short combat episode has no measured scenery movement, so it does not verify physical scrolling.</p>
<p>Raw FL/FR:</p><audio controls src="raw-context.wav"></audio><p>Decoded OBS AAC:</p>
<audio controls src="aac-context.wav"></audio><table><tr><th>OBS start (s)</th><th>AAC zero (ms)</th>
<th>Nearest raw zero (ms)</th></tr>'''+gaps+'''</table>
<video controls preload="metadata" src="../'''+video.name+'''"></video><div class="grid">'''+''.join(panels)+'''</div>
<h2>Untouched emulator frames</h2><div class="grid">'''+''.join(cards)+'''</div>
<h2>Same-command NES/SNES audio</h2><p>Native rates and original sample values. NES executes the same
ordered writes at packet-publication frames, not original within-frame CPU timing.</p>'''+''.join(players)+'''
<p><a href="report.json">All hashes, sample windows and limits</a> · '''+links+''' ·
<a href="../main-phase-rival-review-819/">Evidence hub</a></p></html>''')
    print(json.dumps(dict(out=str(out),stable_loops=count,frames=len(cards)+len(panels),
                         release_ready=False)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('normal','nes','cadence','transport','nmi','camera','background','raw-audit',
                 'boot','coordinator','video','handoff','snac','out'):
        p.add_argument('--'+name,type=Path,required=True)
    publish(**vars(p.parse_args()))
