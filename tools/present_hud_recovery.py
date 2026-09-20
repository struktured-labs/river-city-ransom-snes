"""Publish unchanged HUD screenshots for the targeted recovery, retaining limits."""
import argparse
import json
from pathlib import Path
import shutil
from tools.benchmark_report import sha


def present(out):
    if out.exists():raise ValueError('Fresh output required')
    proof=Path('build/hud-recovery-3770/report.json')
    report=json.loads(proof.read_text())
    for p,h in report['sources'].items():
        if sha(p)!=h:raise ValueError('Changed HUD evidence')
    sources={str(proof):sha(proof),str(Path(__file__)):sha(Path(__file__))}
    arms=[('Qualified parent3695','audio-prefix-normal-3730'),
          ('Search-only3755: still late','consumer-suffix-normal-3756'),
          ('Post-row stop3764: recovered','postrow-stop-normal-3765')]
    out.mkdir(parents=True)
    body='<!doctype html><meta charset="utf-8"><title>HUD recovery3764</title><style>body{background:#091016;color:#eef;font:17px/1.6 system-ui;max-width:1300px;margin:30px auto}a{color:cyan}.grid{display:flex;gap:12px}figure{flex:1;margin:0}img{width:100%;image-rendering:pixelated}</style><h1>Two HUD updates recovered; broader qualification remains</h1><p>Experimental3764. Original graphics and queue order unchanged. Faster suffix search, row cutoff252, post-transfer scan stop. Final palette cutoff254 unchanged. No deployment.</p><p>The first trial remained late; the second published the HUD but skipped final palettes. The combined gate rejects both real negatives. Candidate3764 publishes both target rows and executes all five final palette transfers in both cases.</p>'
    for f in (2473,2485):
        body+=f'<h2>Frame {f}</h2><div class="grid">'
        for i,(label,folder) in enumerate(arms):
            root=Path('build/overflow-3526')/folder
            rows=json.loads((root/'timeline.json').read_text());r=rows[f-1]
            p=root/r['frame_image']
            if sha(p)!=r['frame_image_sha256']:raise ValueError('Changed frame')
            sources[str(p)]=sha(p);sources[str(root/'timeline.json')]=sha(root/'timeline.json')
            target=f'{i}-{f}.png';shutil.copyfile(p,out/target)
            body+=f'<figure><img src="{target}" alt="{label}, frame{f}"><figcaption>{label}</figcaption></figure>'
        body+='</div>'
    body+='<p>This proves two event deadlines, not all graphics. All86 changed prefix pictures, including boot/menu changes, remain unresolved as a whole. Sound-packet spacing improves to11.19–22.16ms versus9.85–23.71ms in the same short route; not a pop-free or hardware claim.</p><p><a href="../hud-recovery-3770/report.json">Exact gates and rejected variants</a> · <a href="../postrow-audio-review-3772/">All changed pictures and native audio</a> · <a href="https://github.com/struktured-labs/river-city-ransom-snes/issues/18">Issue18</a> · <a href="../progress-3728/">Progress</a></p>'
    (out/'index.html').write_text(body)
    (out/'report.json').write_text(json.dumps(dict(sources=sources,
        artifacts={p.name:sha(p) for p in out.iterdir()},release_ready=False),indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    present(**vars(parser.parse_args()))
