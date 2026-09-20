"""Actual integrated-game cadence, ready gaps and untouched audio after fast polling."""
from bisect import bisect_right
import csv
import html
import json
from pathlib import Path
import shutil
import statistics
from tools.audit_busy_combat import classify
from tools.benchmark_report import sha,verify_capture
from tools.review_command_priority import bound


def main():
    root=Path('build/timed-token-grace-full-observed-4114');normal=Path('build/timed-token-grace-full-4113')
    out=Path('build/timed-token-grace-review-4115')
    if out.exists():raise ValueError('Fresh review required')
    bound(root/'flushed-capture.json');r=bound(root/'timed-game-audio.json')
    a,rows=verify_capture(normal);b,observed=verify_capture(root)
    if rows!=observed or a['audio_sha256']!=b['audio_sha256']:raise ValueError('Non-neutral observer')
    starts=[x['audio_start_sample'] for x in rows];stable=[];excluded=[]
    for i,(t,u) in enumerate(zip(r['ready_ticks'],r['ready_ticks'][1:])):
        first=bisect_right(starts,(t+4)//32);last=bisect_right(starts,(u+4)//32)
        x=dict(event=i+1,first=first,last=last,tick=t,next_tick=u,gap_ms=(u-t)*1000/(32040*32))
        if not 1<=first<=last<=len(rows):excluded.append(dict(x,reason='outside_timeline'));continue
        x['context']=classify(rows[first-1:last]);(stable if x['context']['room'] is not None else excluded).append(x)
    gaps=[x['gap_ms'] for x in stable]
    summary=dict(r['summary'],cadence_passed=r['cadence']['passed'],gap_min_ms=min(gaps),gap_max_ms=max(gaps),
        gap_median_ms=statistics.median(gaps),stable_intervals=len(stable),excluded_intervals=len(excluded),
        replay_seconds=r['replay_seconds'],total_seconds=r['total_seconds'],rom_sha256=a['rom_sha256'])
    old=bound(Path('build/integrated-timed-audio-review-4103/report.json'))
    out.mkdir();shutil.copyfile(normal/'audio.wav',out/'native-game-audio.wav')
    pictures=[]
    for name in ('right_02','observe_shop','park_00_east_settle','park_00_west_settle'):
        seg=next(x for x in a['segments'] if x['name']==name);frame=seg['end_frame']
        path=normal/rows[frame-1]['frame_image'];dest=out/(name+'.png');shutil.copyfile(path,dest)
        pictures.append(f'<figure><img src="{dest.name}"><figcaption>{name} · frame {frame}</figcaption></figure>')
    table=''.join(f'<tr><td>{k}</td><td>{v["intervals"]}</td><td>{html.escape(str(v["frame_histogram"]))}</td><td>{v["passed"]}</td></tr>' for k,v in summary['rooms'].items())
    page='''<!doctype html><meta charset="utf-8"><title>Integrated audio fast-poll candidate4108</title>
<style>body{background:#101721;color:#e2edf7;font:18px system-ui;max-width:1120px;margin:35px auto;padding:20px}a{color:#6cdbea}td,th{padding:10px;text-align:left;border-bottom:1px solid #445}.scenes{display:flex;flex-wrap:wrap}figure{margin:12px}img{width:256px;image-rendering:pixelated}figcaption{max-width:256px;font-size:14px}audio{width:100%}p{line-height:1.5}pre{white-space:pre-wrap}</style>
<h1>Integrated audio: bounded fast polling</h1><p>Candidate4108. Offline gameplay evidence, not physical-console approval.</p>
<p>A16-iteration SPC token-arrival window avoids expensive idle sound work between rapidly arriving packet bytes. Stalled transfers still service timers and envelopes. This changes the integrated receiver, not the emulator scheduler.</p>
<h2>Full route: game-loop cadence</h2><table><tr><th>Room</th><th>Intervals</th><th>Frames per interval: count</th><th>Gate</th></tr>'''+table+'''</table>
<p>Previous4098 had12three-frame mall intervals and a33.833ms maximum stable ready gap. Different encounters are retained: this is not a matched-NES speed comparison. Current full observer-on/off timeline and native PCM match exactly.</p>
<h2>Untouched native game audio</h2><audio controls preload="metadata" src="native-game-audio.wav"></audio>
<p>No trimming, retiming, alignment, normalization or resampling in this report. Clipping and ready spacing alone do not certify acoustic fidelity or no popping. Old direct-receiver packet IDs are not valid for staged copy.</p>
<h2>Candidate-only scene audit</h2><div class="scenes">'''+''.join(pictures)+'''</div>
<h2>Measured result</h2><pre>'''+html.escape(json.dumps(summary,indent=2))+'''</pre>
<p>Still open: staged sound-onset/restart ordering, broader graphics and combat regression checks, matched original-NES timing and physical SNES Junior/EverDrive acceptance. No hardware deployment or default-ROM replacement.</p>
<p><a href="report.json">All ready gaps, excluded intervals and bindings</a> · <a href="../integrated-timed-audio-review-4103/">Previous failed build</a> · <a href="https://github.com/struktured-labs/river-city-ransom-snes/issues/6">Audio issue #6</a></p>'''
    (out/'index.html').write_text(page)
    paths=[Path(__file__),Path('tools/audit_busy_combat.py'),root/'timed-game-audio.json',root/'flushed-capture.json',
        root/'capture.json',normal/'capture.json',Path('build/integrated-timed-audio-review-4103/report.json')]
    (out/'report.json').write_text(json.dumps(dict(summary=summary,previous=old['summary'],stable=stable,excluded=excluded,
        sources={str(p):sha(p) for p in paths},artifacts={p.name:sha(p) for p in out.iterdir()},release_ready=False,
        scope=__doc__),indent=2)+'\n')
    print(json.dumps(summary))


if __name__=='__main__':main()
