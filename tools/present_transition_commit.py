"""Compact browser view of immutable transition3517 evidence; no new verdicts."""
import argparse
import html
import json
from pathlib import Path
import shutil

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha


def present(source,out):
    if out.exists():raise ValueError('Fresh presentation required')
    report=bound_report(source/'report.json')
    for p,h in report['artifacts'].items():
        if sha(source/p)!=h:raise ValueError('Changed report artifact')
    s=report['summary'];a=s['audio'];d=s['dma'];r=s['full_renderer']
    rooms=report['audio_and_cadence']['cadence']['rooms']
    room_stats={k:{name:v[name] for name in ('intervals','frame_histogram','busy_intervals','passed')} for k,v in rooms.items()}
    out.mkdir();cards=[]
    for name in ('parent','candidate'):
        for suffix in ('last-black','first-visible'):
            filename=f'{name}-{suffix}.png';shutil.copyfile(source/filename,out/filename)
            cards.append(f'<figure><img src="{filename}"><figcaption>{name} — {suffix}</figcaption></figure>')
    body='<!doctype html><meta charset="utf-8"><title>Transition commit: audit summary</title><style>body{background:#101821;color:#eef;font:17px system-ui;max-width:1120px;margin:30px auto}a{color:#9df}.grid{display:grid;grid-template-columns:1fr 1fr}figure{margin:12px}img{width:384px;image-rendering:pixelated}td,th{text-align:left;padding:8px;border-bottom:1px solid #456}pre{white-space:pre-wrap}</style>'
    body+='<h1>Room-transition handoff — offline candidate3502</h1><p>Readiness now commits with final display admission. Equivalent direct-page flag reads save64 CPU cycles; deadline remains254. No graphics or sound assets changed.</p>'
    body+='<p><strong>Not deployed or release-ready.</strong> Normal fade duration is unchanged. Original-NES speed, subjective popping, menu regressions and the remaining HUD publication delay are not certified here.</p>'
    body+=f'<p><a href="../{source.name}/report.json">Complete immutable evidence, all primary differences and rejected builds</a> · <a href="report.json">Presentation bindings</a></p>'
    body+='<table><tr><th>Check</th><th>Observed result</th></tr>'
    rows=[('Route',f'{s["full_frames"]:,} frames; same-core observer/control equality'),
          ('Playfield renderer',f'{r["eligible_frames"]:,} eligible frames; zero missing coverage, splits or stale-camera failures'),
          ('DMA',f'{d["dma_transfers"]:,} safe whole transfers; latest visible end line{d["latest_visible_end"]}'),
          ('Sprite source cohort',f'{s["sprite_generations"]} generations rendered next frame; later/censored sources retained'),
          ('Audio startup',f'{a["restarts"]:,} restarts / {a["packets"]:,} commands; all64 phases; no tested startup-order failures'),
          ('Native PCM',f'{a["samples"]:,} stereo samples; no clipping. Not a claim of pop-free sound.'),
          ('Normal transition fade','20 black frames before and after; room entry→first picture21 frames in both'),
          ('Negative controls','Cutoff254 rollback stalls at boot; cutoff255 triggers VBlank overrun; both retained')]
    body+=''.join('<tr><td>'+html.escape(k)+'</td><td>'+html.escape(v)+'</td></tr>' for k,v in rows)+'</table>'
    body+='<h2>Main-loop cadence</h2><p>Busy-inclusive intervals by room (two display frames per measured iteration). This is not matched original-NES speed proof.</p><pre>'+html.escape(json.dumps(room_stats,indent=2))+'</pre>'
    body+='<h2>Last black frame / first visible picture</h2><p>The first visible picture is identical. The candidate boots one frame later; no primary timeline was aligned to manufacture equality.</p><div class="grid">'+''.join(cards)+'</div>'
    body+='<p><a href="../transition-direct-full-normal-3506/audio.wav">Native full-route WAV</a></p><audio controls preload="none" src="../transition-direct-full-normal-3506/audio.wav"></audio>'
    (out/'index.html').write_text(body)
    result=dict(source_report=str(source/'report.json'),checks=report['checks'],release_ready=False,
        sources={str(source/'report.json'):sha(source/'report.json'),str(Path(__file__)):sha(Path(__file__))},
        artifacts={p.name:sha(p) for p in out.iterdir()},scope=__doc__)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),checks=report['checks'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('source','out'):p.add_argument('--'+k,type=Path,required=True)
    present(**vars(p.parse_args()))
