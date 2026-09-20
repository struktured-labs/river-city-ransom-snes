"""Integrated game evidence: retain failed controls, native audio and all ready gaps."""
from bisect import bisect_right
import html
import json
from pathlib import Path
import shutil
import statistics
from tools.audit_busy_combat import classify
from tools.benchmark_report import sha,verify_capture
from tools.review_command_priority import bound


def main():
    out=Path('build/integrated-timed-audio-review-4103')
    if out.exists():raise ValueError('Fresh output required')
    normal=Path('build/timed-no-duplicate-full-4101');obs=Path('build/timed-no-duplicate-full-observed-4102')
    report=bound(obs/'timed-game-audio.json');receipt,rows=verify_capture(normal)
    observed,orows=verify_capture(obs)
    if rows!=orows or receipt['audio_sha256']!=observed['audio_sha256'] or not report['summary']['observer_neutral']:
        raise ValueError('Observer changed primary timeline/PCM')
    starts=[r['audio_start_sample'] for r in rows];stable=[];excluded=[]
    for i,(t,u) in enumerate(zip(report['ready_ticks'],report['ready_ticks'][1:])):
        first=bisect_right(starts,(t+4)//32);last=bisect_right(starts,(u+4)//32)
        item=dict(event=i+1,first=first,last=last,tick=t,next_tick=u,gap_ms=(u-t)*1000/(32040*32))
        if not 1<=first<=last<=len(rows):
            excluded.append(dict(item,reason='outside_primary_timeline'));continue
        context=classify(rows[first-1:last]);item['context']=context
        (stable if context['room'] is not None else excluded).append(item)
    gaps=[r['gap_ms'] for r in stable]
    summary=dict(report['summary'],cadence_passed=report['cadence']['passed'],
        gap_min_ms=min(gaps),gap_median_ms=statistics.median(gaps),gap_max_ms=max(gaps),
        stable_intervals=len(stable),excluded_intervals=len(excluded),rom_sha256=receipt['rom_sha256'])
    out.mkdir();shutil.copyfile(normal/'audio.wav',out/'native-game-audio.wav')
    cards=[]
    for name in ('right_02','observe_shop','park_00_east_settle','park_00_west_settle'):
        seg=next(s for s in receipt['segments'] if s['name']==name);frame=seg['end_frame'];r=rows[frame-1]
        source=normal/r['frame_image'];dest=out/(name+'.png');shutil.copyfile(source,dest)
        cards.append(f'<figure><img src="{dest.name}"><figcaption>{html.escape(name)} · frame {frame}</figcaption></figure>')
    rooms=''.join(f'<tr><td>{k}</td><td>{v["intervals"]}</td><td>{html.escape(str(v["frame_histogram"]))}</td><td>{v["passed"]}</td></tr>' for k,v in summary['rooms'].items())
    body='''<!doctype html><meta charset="utf-8"><title>Integrated audio candidate 4098</title>
<style>body{background:#101721;color:#e2edf7;font:18px system-ui;max-width:1120px;margin:35px auto;padding:20px}a{color:#6cdbea}td,th{padding:10px;text-align:left;border-bottom:1px solid #445}.scenes{display:flex;flex-wrap:wrap}figure{margin:12px}img{width:256px;image-rendering:pixelated}figcaption{max-width:256px;font-size:14px}audio{width:100%}p{line-height:1.5}pre{white-space:pre-wrap}</style>
<h1>The buffered audio engine is now in the game</h1>
<p>Candidate4098, offline experiment. No MiSTer restart, default-ROM replacement, or hardware-release approval.</p>
<p>New SPC packet staging, per-packet beam-relative deadline, echo-safe boot, timer-driven transfer service, and removal of duplicate pre-arm work. Original graphics and game logic are not intentionally edited.</p>
<h2>Actual full-route result</h2><table><tr><th>Room</th><th>Intervals</th><th>Frames per interval: count</th><th>Cadence gate</th></tr>'''+rooms+'''</table>
<p>Same-core observer reproduces the complete primary timeline and native audio exactly. Different encounters and route lengths prevent a matched-original-NES speed claim. Earlier immediate-staging4084 completed but had12three-frame school intervals; delayed4079 failed the park endpoint. Those failures remain retained.</p>
<h2>Native game audio</h2><audio controls preload="metadata" src="native-game-audio.wav"></audio>
<p>Full untouched capture: no trimming, alignment, normalization or resampling by this report. No clipping is not a pop-free certificate. Ready-event spacing measures engine timing, not individual sound-onset fidelity.</p>
<h2>Candidate-only scene audit</h2><div class="scenes">'''+''.join(cards)+'''</div>
<h2>Measurements and remaining work</h2><pre>'''+html.escape(json.dumps(summary,indent=2))+'''</pre>
<p>Still required: exact source-to-sound latency and restart ordering for staged packets, broader sprite/text/palette/scroll qualification, matched NES performance, listening acceptance and Junior/EverDrive validation. No user-test recommendation yet.</p>
<p><a href="report.json">Every ready gap, exclusions and bindings</a> · <a href="https://github.com/struktured-labs/river-city-ransom-snes/issues/6">Audio issue #6</a> · <a href="../progress-3728/">Project dashboard</a></p>'''
    (out/'index.html').write_text(body)
    paths=[Path(__file__),Path('tools/audit_busy_combat.py'),normal/'capture.json',obs/'timed-game-audio.json',obs/'capture.json']
    (out/'report.json').write_text(json.dumps(dict(summary=summary,stable=stable,excluded=excluded,
        sources={str(p):sha(p) for p in paths},artifacts={p.name:sha(p) for p in out.iterdir()},
        release_ready=False,scope=__doc__),indent=2)+'\n')
    print(json.dumps(summary))


if __name__=='__main__':main()
