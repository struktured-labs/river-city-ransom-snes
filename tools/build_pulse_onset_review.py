"""Publish source-bound DSP onset evidence beside a real Rival trial."""
import argparse
import html
import json
from pathlib import Path
import shutil

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha


def paired_events(report):
    def keyed(side):
        events = side['events']
        result = {(e['packet'], e['voice']): e for e in events}
        if len(result) != len(events):
            raise ValueError('Duplicate onset identity')
        return result
    before, after = (keyed(report[s]) for s in ('baseline', 'candidate'))
    if before.keys() != after.keys() or any(
            before[k]['target_pitch'] != after[k]['target_pitch'] for k in before):
        raise ValueError('Different restart identities or target pitches')
    return [(e, after[k]) for k, e in sorted(before.items(),
        key=lambda item: (-len(item[1]['stale_nonzero_voice_samples']), item[0]))]


def build(out):
    paths = dict(onset=Path('build/pulse-onset-audit-1342/report.json'),
        cadence=Path('build/postpublish-cadence-1327/report.json'),
        audio=Path('build/postpublish-audio-1361/report.json'),
        capture=Path('build/postpublish-gameplay-1352/report.json'),
        camera=Path('build/postpublish-camera-1362/report.json'))
    reports = {k: bound_report(p) for k, p in paths.items() if k != 'camera'}
    camera = reports['camera'] = json.loads(paths['camera'].read_text())
    video = Path('build/postpublish-gameplay-1360.mp4')
    if (sha(video) != camera['video_sha256'] or
            sha(Path('tools/audit_physical_camera.py')) != camera['implementation_sha256'] or
            not all(camera['matcher_controls'].values()) or
            not reports['onset']['passed'] or not reports['cadence']['passed']):
        raise ValueError('Changed video/implementation or failed audit')
    pairs = paired_events(reports['onset'])
    out.mkdir(parents=True, exist_ok=False)
    sources = {str(Path(__file__)): sha(Path(__file__))}

    def copy(path, name=None):
        name = name or path.name
        shutil.copyfile(path, out/name)
        sources[str(path)] = sha(path)
        return name

    for name, path in paths.items():
        copy(path, name+'.json')
    copy(video, 'rival.mp4')
    plots = []
    for before, after in pairs[:3]:
        svg = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 520">',
               '<rect width="1200" height="520" fill="white"/>',
               '<g font-family="sans-serif" font-size="14" fill="#123">',
               f'<text x="40" y="24">Packet {before["packet"]}, voice {before["voice"]}: measured DSP startup; gray line = first oscillator advance</text>']
        pitch_max = max(s['pitch'] for e in (before, after) for s in e['samples']) or 1
        output_max = max(abs(s['output']) for e in (before, after) for s in e['samples']) or 1
        for column, (label, event) in enumerate((('Before', before), ('After', after))):
            samples = event['samples']
            left = 40+600*column
            x = lambda i: left+5*i
            py = lambda p: 240-150*p/pitch_max
            oy = lambda o: 380-75*o/output_max
            stale = event['stale_nonzero_voice_samples']
            pitch_points = []
            for i, s in enumerate(samples):
                if i:
                    pitch_points.append(f'{x(i)},{py(samples[i-1]["pitch"])}')
                pitch_points.append(f'{x(i)},{py(s["pitch"])}')
            output_points = ' '.join(f'{x(s["index"])},{oy(s["output"])}' for s in samples)
            svg.extend([f'<text x="{left}" y="55">{label}: {len(stale)} stale nonzero samples</text>',
                f'<text x="{left}" y="78">Pitch 0–{pitch_max}; orange target {event["target_pitch"]}</text>',
                f'<line x1="{x(6)}" x2="{x(6)}" y1="85" y2="460" stroke="gray" stroke-dasharray="3"/>',
                f'<line x1="{left}" x2="{x(95)}" y1="{py(event["target_pitch"])}" y2="{py(event["target_pitch"])}" stroke="orange"/>',
                '<polyline points="'+' '.join(pitch_points)+'" fill="none" stroke="#1670b0"/>',
                f'<text x="{left}" y="280">Post-envelope output ±{output_max}; red = stale pitch</text>',
                f'<line x1="{left}" x2="{x(95)}" y1="380" y2="380" stroke="#ddd"/>',
                f'<polyline points="{output_points}" fill="none" stroke="#1670b0"/>',
                f'<text x="{left}" y="495">Sample index 0–95 after actual KON consumption</text>'])
            svg.extend(f'<circle cx="{x(s["index"])}" cy="{oy(s["output"])}" r="2.5" fill="red"/>' for s in stale)
        svg.append('</g></svg>')
        name = f'onset-{before["packet"]}-{before["voice"]}.svg'
        (out/name).write_text(''.join(svg))
        plots.append(f'<img src="{name}" alt="Measured DSP startup before and after">')
    figures = []
    for name, label in [('postpublish-paused-1351', 'Before traversal'),
                        ('postpublish-aftertrial-1353', 'After traversal'),
                        ('postpublish-snac-restored-1357', 'SNAC restored Yes'),
                        ('postpublish-handoff-1359', 'Paused handoff; OSD closed')]:
        path = Path('build')/(name+'.png')
        if not path.exists():
            raise ValueError('Missing unchanged screenshot: '+str(path))
        copy(path)
        figures.append(f'<figure><a href="{path.name}"><img src="{path.name}"></a><figcaption>{label}</figcaption></figure>')
    players = []
    for path, meta in reports['audio']['clips'].items():
        path = Path(path)
        if sha(path) != meta['sha256']:
            raise ValueError('Native audio clip changed')
        copy(path)
        players.append(f'<p>{html.escape(path.stem)} — original 48 kHz samples</p><audio controls src="{path.name}"></audio>')
    rows = ''.join(f'<tr><td>{label}</td><td>{reports["onset"]["baseline"][key]}</td>'
        f'<td>{reports["onset"]["candidate"][key]}</td></tr>' for key, label in
        [('restarts', 'Game voice restarts'), ('wrong_first_pitch', 'Wrong first oscillator pitch (eligible voices)'),
         ('stale_nonzero_onsets', 'Onsets with nonzero output at stale pitch'),
         ('stale_nonzero_samples', 'Total stale nonzero samples')])
    page = '''<!doctype html><meta charset="utf-8"><title>Pulse startup fix · Rival test</title>
<style>body{background:#10141b;color:#e4edf4;font:17px/1.5 system-ui;max-width:1200px;margin:30px auto;padding:20px}
a{color:#72d9ee}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:16px}
img,video,audio{width:100%}figure{margin:0}td,th{padding:8px;border:1px solid #506070}table{border-collapse:collapse}
.open{border-left:4px solid #ffc16a;padding-left:14px}</style>
<h1>Pulse startup fix: measured internally, trialed on Rival</h1>
<p>September 18, 2026 · test ROM <code>fa882cb61138</code>. Graphics unchanged. Previous cartridge retained.</p>
<h2>The defect and repair</h2><p>Pulse restart previously preceded publication of the new pitch.
The patch accumulates the restart mask and issues KON after voice setup, before ready.
Only 45 ROM bytes differ, confined to SPC code and checksum; CPU game code and graphics remain unchanged.</p>
<table><tr><th>Identical-command replay</th><th>Before</th><th>After</th></tr>'''+rows+'''</table>
<p>All 2,512 received packets match byte-for-byte. Every KON consumption and all 96 following voice samples
are observed at their actual DSP phases. Startup delay and 32-clock sample spacing are checked.
The observer leaves complete PCM, timeline, RAM and final picture unchanged. Raw DAC equals delivered PCM.
Wrong-pitch and missing-sample derived controls are rejected. The target is the packet's final DSP pitch,
not an independently synthesized NES waveform.</p>'''+''.join(plots)+'''
<p class="open">This proves a startup defect and its repair, not global pop-free sound or BRR-start fidelity.
The earlier full-mix sample-step metric was mixed (84 improved, 2 unchanged, 141 worse), and remains
<a href="../postpublish-audio-review-1330/">available with native A/B clips</a>. Pulse/noise edges are not a perceptual click verdict.</p>
<h2>Actual Rival gameplay recording</h2><video controls preload="metadata" src="rival.mp4"></video>
<p>Bounded 22.7-second input episode inside a 30-second dual recording: unpause, right/jump, left/jump, pause.
Video and AAC are stream copies, not re-encoded. SNAC was temporarily disabled for USB input and restored afterward.</p>
<p>1,790 decoded frames; 1,783 accepted scenery pairs and six rejected pairs retained.
Equal-step holds: 26 two-frame and eight 26-frame holds; no short 1/3/4-frame holds in this route.
The earlier physical four-frame hold is not resolved by its absence in this different encounter.</p>
<p>The emulator regression retains 3,550 stable loops across school/alley/mall/park, all two ticks with
two-frame consecutive starts. No short irregular park holds. This is not equal-work full-game speed certification.</p>
<h2>Audio independently checked against the raw capture branch</h2>
<p>One fixed offset, fitted on seconds 4–7 only. Five held-out waveform correlations: 0.99863–0.99931.
Dead-monitor negative and injected 100 ms AAC-only dropout are detected. Both branches share Blackmagic/OBS:
agreement validates capture, not hardware synthesis fidelity.</p>'''+''.join(players)+'''
<p class="open">Two short AAC silences at 8.916 s (10.67 ms) and 9.1027 s (24 ms) also exist in raw audio
(19.31 ms and 29.94 ms). Their game-command cause remains unverified. Pause-adjacent and recording-edge
silences are retained in the complete report. No pop-free claim.</p>
<h2>Untouched capture collage</h2><div class="grid">'''+''.join(figures)+'''</div>
<p>Handoff: paused school street, SNAC Yes, OSD closed. Owned recordings stopped; debug tap removed;
saved SNES configuration and OBS routing restored. Controller presets and splash sound were not changed.</p>
<p><a href="onset.json">Every DSP onset</a> · <a href="cadence.json">Speed regression</a> ·
<a href="camera.json">All physical camera pairs</a> · <a href="audio.json">Raw/AAC audit</a> ·
<a href="capture.json">Input/recording receipt</a> · <a href="manifest.json">Artifact hashes</a></p>'''
    (out/'index.html').write_text(page)
    (out/'manifest.json').write_text(json.dumps(dict(sources=sources,
        artifacts={p.name: sha(p) for p in out.iterdir() if p.is_file()},
        release_ready=False, pop_free_verified=False), indent=2)+'\n')
    print(json.dumps(dict(out=str(out), paired_onsets=len(pairs))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    build(**vars(parser.parse_args()))
