"""Publish scoped timed-receiver results and byte-identical native audio."""
import html
import json
from pathlib import Path
import shutil
from tools.review_command_priority import bound
from tools.benchmark_report import sha


def main():
    out=Path('build/timed-settled-review-4072')
    if out.exists():raise ValueError('Fresh output required')
    roots={
        'failed_stream':Path('build/timed-idle-qualification-4067'),
        'stream':Path('build/timed-settled-qualification-4069'),
        'cases':Path('build/timed-settled-check-4070'),
        'old_audio':Path('build/timed-envelope-old-audio-4065'),
        'new_audio':Path('build/timed-settled-audio-4071')}
    reports={k:bound(v/'report.json') for k,v in roots.items()}
    for root in ('build/timed-receiver-fixture-4060','build/timed-idle-receiver-fixture-4063','build/timed-settled-receiver-fixture-4068'):
        bound(Path(root)/'manifest.json')
    bound(Path('.deps/snes9x-timed-receiver-4061/timed-core.json'))
    bound(Path('.deps/snes9x-staged-receiver-4055/staged-core.json'))
    if reports['failed_stream']['passed'] or not reports['stream']['passed'] or not reports['cases']['passed']:
        raise ValueError('Unexpected qualification result')
    out.mkdir();rows=[]
    for key,label in (('old_audio','Frozen envelope — 4060'),('new_audio','Envelope + deadline fix — 4068')):
        root=roots[key];r=reports[key];wav=root/'native-audio.wav'
        if sha(wav)!=r['artifacts'][wav.name]:raise ValueError('Changed audio')
        shutil.copyfile(wav,out/(key+'.wav'));s=r['summary']
        rows.append(f'<tr><td>{label}</td><td>{s["advancing_packets"]}/64</td><td>{s["samples"]}</td><td>{s["clipped"]}</td><td><audio controls src="{key}.wav"></audio></td></tr>')
    controls=''.join(f'<li>{html.escape(k)}: rejected</li>' for k in reports['stream']['controls'])
    page='''<!doctype html><meta charset="utf-8"><title>Timed audio receiver — 4072</title>
<style>body{background:#101721;color:#e2edf7;font:18px system-ui;max-width:1100px;margin:40px auto;padding:20px}a{color:#6cdbea}td,th{padding:12px;text-align:left;border-bottom:1px solid #445}audio{width:260px}p{line-height:1.5}</style>
<h1>Audio buffering: two prototype bugs fixed</h1>
<p>Offline SPC700 fixture only. No game ROM changed or hardware deployment. Not a gameplay sputter fix or release approval.</p>
<h2>What changed</h2><p>Legacy envelopes now advance while packets wait. Before arming a new deadline, the receiver accounts for all old Timer0 ticks without resetting the timer or discarding sound updates.</p>
<p>The earlier repeated stream failed five early deadlines. Corrected 4068 passes 202 sequential varied packets and 192 isolated timing cases. Tests took 0.086 and 0.238 seconds respectively; compilation excluded. Earlier failed evidence is retained.</p>
<h2>Native audio — full, unaligned captures</h2><table><tr><th>Version</th><th>Envelopes advancing during hold</th><th>Stereo frames</th><th>Clipped samples</th><th>Listen</th></tr>'''+''.join(rows)+'''</table>
<p>32,040 Hz native DSP PCM, packaged byte-for-byte. No trimming, alignment, normalization or resampling. Different durations reflect changed execution costs. Both peaks are 2307 and maximum adjacent steps 4152; those figures do not establish pop-free sound. Terminal DSP backlog is not forced to flush. Envelope counts come from executed state snapshots, not listening judgments.</p>
<h2>Actual broken-code controls</h2><ul>'''+controls+'''</ul>
<h2>Still required</h2><p>CPU/SPC presentation-clock integration, original-NES timing and sound comparisons, native game-audio qualification, graphics/speed tradeoff tests, and physical SNES Junior/EverDrive validation.</p>
<p><a href="https://github.com/struktured-labs/river-city-ransom-snes/issues/6">Audio issue #6</a> · <a href="../progress-3728/">Project dashboard</a> · <a href="report.json">Report and bindings</a></p>'''
    (out/'index.html').write_text(page)
    paths=[Path(__file__)]+[v/'report.json' for v in roots.values()]
    report=dict(scope=__doc__,sources={str(p):sha(p) for p in paths},
        artifacts={p.name:sha(p) for p in out.iterdir()},fixture_only=True,release_ready=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(out)


if __name__=='__main__':main()
