"""Compact, byte-identical media export of the immutable mixed-consumer audit."""
import argparse
import html
import json
from pathlib import Path
import shutil
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha


def publish(source,out):
    if out.exists():raise ValueError('Fresh export required')
    report=bound_report(source/'report.json')
    for p,h in report['artifacts'].items():
        if sha(source/p)!=h:raise ValueError('Changed reviewed artifact')
    s=report['summary'];out.mkdir();cards=[]
    for name in ('parent3527-8245.png','mixed3583-8245.png','native-audio.wav'):
        shutil.copyfile(source/name,out/name)
        if sha(source/name)!=sha(out/name):raise ValueError('Changed exported media')
        if name.endswith('.png'):
            cards.append(f'<figure><img src="{name}"><figcaption>{"Before3527" if name.startswith("parent") else "After3583"}: exact frame8245</figcaption></figure>')
    rows=[('Health source → picture','5 → 3 frames'),('Dialogue publication','All11 glyphs in2–3frames; individual timing differs'),
          ('Fresh boot / full route',f'{s["boot_frames"]} / {s["full_frames"]} frames'),
          ('Sprites',f'{s["sprite_generations"]} known source generations, all next-frame'),
          ('General DMA',f'{s["dma_transfers"]} safe envelopes; latest visible end line{s["latest_visible_dma_end"]}'),
          ('Scrolling renderer',f'{s["renderer_eligible"]} eligible frames; no observed split/stale-camera/coverage failures'),
          ('Graphics pattern uploads','Actual original source bytes in VRAM after2/3frames; longest pending span3'),
          ('Audio startup',f'{s["audio"]["packets"]} commands / {s["audio"]["restarts"]} restarts / {s["audio_phases"]} startup phases pass'),
          ('Stable game loops','3668 measured intervals of2frames; not matched original-NES proof')]
    body='<!doctype html><meta charset="utf-8"><title>RCR: faster HUD publication</title><style>body{background:#101821;color:#eef;font:17px system-ui;max-width:1080px;margin:25px auto}a{color:#9df}.pair{display:grid;grid-template-columns:1fr 1fr}figure{margin:8px}img{width:100%;image-rendering:pixelated}td{padding:7px;border-bottom:1px solid #456}code{overflow-wrap:anywhere}</style>'
    body+='<h1>Health updates: five frames → three</h1><p>Candidate3583 reduces repeated row-queue searches. Original graphics, sound engine and DMA deadlines are unchanged. '
    body+='The exact-state playfield, sprite preparation, counters, cameras and inputs match; full cross-ROM state and PCM do not.</p>'
    body+='<div class="pair">'+''.join(cards)+'</div><h2>Offline checks</h2><table>'
    body+=''.join('<tr><td>'+html.escape(k)+'</td><td>'+html.escape(v)+'</td></tr>' for k,v in rows)+'</table>'
    body+='<h2>Native full-route audio</h2><audio controls preload="none" src="native-audio.wav"></audio>'
    body+=f'<p>Unmodified32040Hz stereo PCM: peak{s["audio"]["peak"]}, largest adjacent step{s["audio"]["max_adjacent_step"]}, no clipping. '
    body+='This is <strong>not a pop-free or subjective hearing verdict</strong>.</p>'
    body+='<p>Not deployed or release-ready. Still required: current menus, both-direction scrolling routes, matched original-game workloads and physical/acoustic acceptance. '
    body+='All failed experiments—including the wrong-instruction-boundary bug—remain in the detailed audit. The real bad helper now fails an integration test.</p>'
    body+=f'<p><a href="../{source.name}/report.json">Detailed immutable audit: all differences, failures and1383 source bindings</a> · '
    body+=f'<a href="../{source.name}/">Expanded comparison</a></p><p>ROM SHA256: <code>{s["rom_sha256"]}</code></p>'
    (out/'index.html').write_text(body)
    sources={str(p):sha(p) for p in (Path(__file__),source/'report.json',source/'native-audio.wav',
        source/'parent3527-8245.png',source/'mixed3583-8245.png')}
    (out/'publication.json').write_text(json.dumps(dict(sources=sources,underlying_checks_passed=report['passed'],
        release_ready=False,artifacts={p.name:sha(p) for p in out.iterdir()}),indent=2)+'\n')
    print(json.dumps(dict(out=str(out),checks_passed=report['passed'],release_ready=False)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('source','out'):p.add_argument('--'+k,type=Path,required=True)
    publish(**vars(p.parse_args()))
