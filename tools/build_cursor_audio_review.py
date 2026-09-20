"""Publish native audio and unaltered full-frame cursor-navigation evidence."""
import argparse
from html import escape
import json
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image
from scipy.io import wavfile

from tools.benchmark_report import sha


# Pinned 1920x1080 OBS scene: cursor slots only, never menu text or game art.
CURSOR_BOXES = ((395,900,421,937),(1095,900,1121,937),(395,974,421,1010),
                (811,974,837,1010),(1262,974,1288,1010))
CURSOR_NAMES = ('Belongings','Password','Level','Status','Help')


def cursor(image):
    if image.shape != (1080,1920,3) or image.dtype != np.uint8:
        raise ValueError('Different pinned OBS geometry/encoding')
    counts = [int(np.all(image[y:b,x:r]>200,axis=2).sum()) for x,y,r,b in CURSOR_BOXES]
    occupied = [i for i,n in enumerate(counts) if n>=250]
    if len(occupied)!=1 or any(n>10 for i,n in enumerate(counts) if i not in occupied):
        raise ValueError('Missing, duplicate or contaminated cursor')
    return dict(index=occupied[0],label=CURSOR_NAMES[occupied[0]],white_pixels=counts)


def publish(audit, out):
    report = json.loads(audit.read_text())
    for path, digest in report['sources'].items():
        if sha(Path(path)) != digest:
            raise ValueError('Changed audit source: '+path)
    out.mkdir(parents=True,exist_ok=False)
    sources = {str(p):sha(p) for p in (audit,Path(__file__),Path('tools/audit_cursor_audio.py'))}
    media = Path(report['media'])
    frames = [120]+[round((e['seconds']+.3)*60) for e in report['runs']['aac']['events']]
    expression = '+'.join(f'eq(n\\,{frame})' for frame in frames)
    subprocess.run(['ffmpeg','-nostdin','-v','error','-n','-i',str(media),'-vf','select='+expression,
        '-vsync','0',str(out/'hardware-%02d.png')],check=True)
    # Decode again and compare every RGB value, not only a generated image hash.
    decoded = subprocess.check_output(['ffmpeg','-nostdin','-v','error','-i',str(media),
        '-vf','select='+expression,'-vsync','0','-f','rawvideo','-pix_fmt','rgb24','-'])
    size = 1920*1080*3
    if len(decoded) != len(frames)*size:
        raise ValueError('Unexpected source frame geometry/count')
    artifacts = {}; panels = []; hardware = []; cursor_negative_controls = {}
    expected_cursors = (0,1,2,3,4,3,2,1,0)
    for index,frame in enumerate(frames,1):
        path = out/f'hardware-{index:02d}.png'
        pixels = np.asarray(Image.open(path).convert('RGB'))
        if pixels.tobytes() != decoded[(index-1)*size:index*size]:
            raise ValueError('Altered source frame')
        observed = cursor(pixels)
        if observed['index'] != expected_cursors[index-1]:
            raise ValueError('Hardware cursor did not consume the declared input')
        if index == 1:
            # Actual-frame copies: a vanished arrow and an extra arrow. No
            # altered panels are published as evidence of real behavior.
            for kind in ('missing','duplicate'):
                mutant = pixels.copy()
                x,y,r,b = CURSOR_BOXES[0 if kind=='missing' else 1]
                mutant[y:b,x:r] = 0 if kind=='missing' else pixels[900:937,395:421]
                caught = False
                try:
                    cursor(mutant)
                except ValueError:
                    caught = True
                cursor_negative_controls[kind] = dict(synthetic=True,detected=caught)
            if not all(v['detected'] for v in cursor_negative_controls.values()):
                raise ValueError('Cursor checker missed a negative control')
        artifacts[path.name] = sha(path)
        description = ('Before navigation' if index == 1 else
                       f'After {"Right" if index <= 5 else "Left"} {index-1 if index<=5 else index-5}')
        hardware.append(dict(path=path.name,frame=frame,seconds=frame/60,description=description,cursor=observed))
        panels.append(f'<figure><a href="{path.name}"><img src="{path.name}" alt="{description}"></a>'
                      f'<figcaption>{description} → {observed["label"]} · source frame {frame}</figcaption></figure>')
    emulator_panels = []
    for label in ('nes','snes'):
        source = next(Path(p).parent for p in report['sources'] if p.endswith('/capture.json') and
                      f'cursor-{label}-' in p and '1038' not in p)
        for index in range(1,5):
            path = source/f'pause_right_visible_{index}.png'
            sources[str(path)] = sha(path)
            emulator_panels.append(f'<figure><a href="../{source.name}/{path.name}">'
                f'<img src="../{source.name}/{path.name}" alt="{label} Right {index}"></a>'
                f'<figcaption>{label.upper()} · Right {index}</figcaption></figure>')
    clips = []
    for clip in report['clips']:
        path = audit.parent/clip['path']
        rate, samples = wavfile.read(path)
        original_rate, original = wavfile.read(clip['source'])
        if (sha(path) != clip['sha256'] or rate != original_rate or
                not np.array_equal(samples,original[clip['first']:clip['last'],clip['channels']])):
            raise ValueError('Audio clip is not the unmodified source samples')
        sources[str(path)] = sha(path)
        clips.append(f'<h3>{escape(path.stem)}</h3><audio controls preload="none" '
                     f'src="../{audit.parent.name}/{path.name}"></audio>')
    rows = []
    for label,run in report['runs'].items():
        events = run['events']
        values = [e['strong_duration_ms'] for e in events]
        rows.append('<tr>'+''.join(f'<td>{escape(str(v))}</td>' for v in
            (label,len(events),f'{min(values):.3f}–{max(values):.3f}',
             f"{max(e['longest_internal_exact_zero_ms'] for e in events):.3f}",run['passed']))+'</tr>')
    mutations = ''.join('<li>'+escape(k)+': '+('detected' if v['detected'] else 'MISSED')+'</li>'
                        for k,v in report['mutations'].items())
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RCR · isolated cursor audio regression</title><style>body{background:#111a23;color:#edf4ff;font:17px system-ui;max-width:1300px;margin:auto;padding:24px}a{color:#8df}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}figure{margin:0}img{width:100%;image-rendering:pixelated}audio{width:100%;max-width:600px}td,th{padding:9px;border:1px solid #456}.open{color:#ffd38c}@media(max-width:700px){.grid{grid-template-columns:1fr}}</style>
<h1>Isolated cursor audio: original NES → SNES emulator → Rival</h1>
<p>September 18 · ROM 071c89e unchanged · no restart. Four Right cues per emulator; four Right then four Left cues on paused Rival. SNAC restored Yes, OSD closed, gameplay still paused by Trash Pick-Up.</p>
<p>All eight real-hardware cues are present in both pre-mute raw PCM and the simultaneous OBS AAC recording. No tested cue contains an internal exact-zero interruption of 2ms or longer. This is a narrow repeated-sound regression, not a combat-audio or perceptual-quality pass.</p>
<table><tr><th>Source</th><th>Cues</th><th>10%-peak span, ms</th><th>Longest internal exact zero, ms</th><th>Coarse cue gates</th></tr>'''+''.join(rows)+'''</table>
<p>Fixed detector: 0.0005 full-scale threshold, 200ms cue separation. Checks require the declared cue count, relative onset residual ≤50ms, 10%-peak span 45–100ms, and no internal exact-zero span ≥2ms. Thresholds are disclosed, not an assertion that the waveforms match. Lower-amplitude filter tails differ and remain audible in the original sample excerpts.</p>
<p>Instrumented SNES replay matches the normal replay's entire frame/RAM/audio timeline and WAV exactly. All '''+str(report['spc_packets'])+''' paired SPC packets match the bytes actually received, with zero mismatches. This is emulator transport evidence, not a hardware APU trace.</p>
<h2>Does the regression detect failures?</h2><p>These five mutations were applied to copies of the actual raw hardware recording; the original is unchanged.</p><ul>'''+mutations+'''</ul>
<h2>Native-rate, unmodified audio</h2><p>No gain matching, resampling, stretching or noise removal. Clips have different leading silence; raw/AAC are separate buffered branches, not game-latency measurements.</p>'''+''.join(clips)+'''
<h2>Hardware navigation: every tap</h2><p>Click any panel for the complete original OBS frame. All pixels were checked against a second decode of the source recording. The game's paused location and actors remain visible throughout. A pinned-scene pixel check independently verifies exactly one cursor and the sequence Belongings → Password → Level → Status → Help → Status → Level → Password → Belongings. Missing-arrow and duplicate-arrow mutations of an actual frame are both rejected.</p><div class="grid">'''+''.join(panels)+'''</div>
<h2>Original NES and port: four Right taps</h2><div class="grid">'''+''.join(emulator_panels)+'''</div>
<h2>Still open</h2><p class="open">The older intermittent mid-combat gaps, pop-free audio, hardware command identity and full-game timing remain unverified. No ROM fix or new build is claimed from this test. Splash sound and controller presets are unchanged.</p>
<p><a href="../'''+audit.parent.name+'''/report.json">Machine-readable audit and source hashes</a> · <a href="report.json">Review provenance</a> · <a href="../main-phase-rival-review-819/">Evidence hub</a></p></html>'''
    (out/'index.html').write_text(page)
    artifacts['index.html'] = sha(out/'index.html')
    result = dict(sources=sources,artifacts=artifacts,hardware_panels=hardware,
                  original_pixels_verified=True,native_audio_samples_verified=True,
                  hardware_cursor_sequence_verified=True,cursor_negative_controls=cursor_negative_controls,
                  release_ready=False)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(hardware_panels=len(frames),emulator_panels=8,native_audio_clips=len(clips))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('audit','out'):
        parser.add_argument('--'+name,type=Path,required=True)
    publish(**vars(parser.parse_args()))
