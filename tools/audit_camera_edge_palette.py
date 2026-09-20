"""Classify actual CGRAM differences only where original shadow and prepared stages agree."""
import argparse
from collections import Counter
import html
import json
from pathlib import Path
import shutil
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha,verify_capture
from tools.capture_sprite_prefix import installed_prefix

STAGES=('shadow','prepared_source','prepared_bg','prepared_obj')


def expected_words(sample):
    bg=bytes.fromhex(sample['prepared_bg']);obj=bytes.fromhex(sample['prepared_obj'])
    if len(bg)!=32 or len(obj)!=32:raise ValueError('Incomplete prepared palette')
    result={i:bg[2*i:2*i+2] for i in range(16)}
    result.update({128+16*p+i:obj[8*p+2*i:8*p+2*i+2] for p in range(4) for i in range(4)})
    return result


def compare(a,b):
    if a['frame']!=b['frame']:raise ValueError('Different frame boundaries')
    changed_stages=[k for k in STAGES if a[k]!=b[k]]
    x,y=bytes.fromhex(a['cgram']),bytes.fromhex(b['cgram'])
    if len(x)!=512 or len(y)!=512:raise ValueError('Need full physical CGRAM')
    wanted=expected_words(b);words=[]
    for i in range(256):
        before,after=x[2*i:2*i+2],y[2*i:2*i+2]
        if before==after:continue
        expected=wanted.get(i)
        verdict=('after_staged' if after==expected else 'before_staged' if before==expected
                 else 'neither_staged') if expected is not None and not changed_stages else 'unsupported'
        words.append(dict(index=i,before=before.hex(),after=after.hex(),
            expected=None if expected is None else expected.hex(),verdict=verdict,
            sprite_transparent_slot=128<=i<192 and i%16==0))
    return dict(frame=a['frame'],changed_stages=changed_stages,words=words)


def audit(baseline,prior,trial,out):
    if out.exists():raise ValueError('Fresh output required')
    sources={};data={};rows={};proofs={};roots=dict(baseline=baseline,prior=prior,trial=trial)
    for name,root in roots.items():
        proof=root/'cgram-pipeline.json';p=bound_report(proof)
        if not p['observer_neutral']:raise ValueError('Need neutral same-core observation')
        control=Path(p['reference'])/'cgram-pipeline.json';c=bound_report(control)
        if not c['parent_core_compatible']:raise ValueError('Missing parent-core compatibility')
        sources.update(p['sources']);sources.update(c['sources'])
        for f in (proof,control):sources[str(f)]=sha(f)
        with installed_prefix('right_08'):receipt,rows[name]=verify_capture(root)
        samples=root/p['samples'];data[name]=json.loads(samples.read_text());proofs[name]=receipt
        if len(data[name])!=len(rows[name]):raise ValueError('Incomplete frame coverage')
    if len({len(v) for v in data.values()})!=1:raise ValueError('Different prefix lengths')
    comparisons={}
    for name in ('prior','trial'):
        records=[compare(a,b) for a,b in zip(data['baseline'],data[name])]
        records=[r for r in records if r['words'] or r['changed_stages']]
        counts=dict(Counter(w['verdict'] for r in records for w in r['words']))
        comparisons[name]=dict(records=records,counts=counts,
            no_observed_stage_regression=not any(r['changed_stages'] for r in records) and
                not any(counts.get(k,0) for k in ('before_staged','neither_staged','unsupported')))
    if comparisons['prior']['no_observed_stage_regression']:
        raise ValueError('Known one-frame delayed fade escaped negative gate')
    a,b=rows['baseline'],rows['trial']
    differences={k:[x['frame'] for x,y in zip(a,b) if x[k]!=y[k]]
                 for k in ('probe_052b','input_requested','input_delivered','video_sha256')}
    report=dict(sources=sources,comparisons=comparisons,differences=differences,
        roms={k:v['rom_sha256'] for k,v in proofs.items()},frames=len(a),release_ready=False,
        scope=__doc__+' All frame/stage changes retained. Equality to staging does not establish '
        'original-NES timing, per-scanline color delivery or correctness of unobserved later scenes. '
        'Raw512-byte CGRAM retained for every frame, including unchanged/hidden/startup states.')
    out.mkdir(parents=True)
    body='<!doctype html><meta charset="utf-8"><title>CGRAM publication comparison</title><style>body{background:#091016;color:#eef;font:17px/1.6 system-ui;max-width:1350px;margin:32px auto}a{color:cyan}.grid{display:flex;gap:12px}figure{margin:0;flex:1}img{width:100%;image-rendering:pixelated}pre{white-space:pre-wrap}</style><h1>Actual palette publication, not just transfer counts</h1><p>Baseline3695, prior3780, trial3819. Every observation preserves its same-core primary video/input/state/nativePCM; new-core compatibility is checked separately. Offline only.</p>'
    body+='<pre>'+html.escape(json.dumps({k:dict(counts=v['counts'],no_observed_stage_regression=v['no_observed_stage_regression']) for k,v in comparisons.items()},indent=2))+'</pre>'
    frames=sorted({r['frame'] for v in comparisons.values() for r in v['records']})
    for f in frames:
        body+=f'<h2>Frame{f}</h2><div class="grid">'
        for name,root in roots.items():
            r=rows[name][f-1];p=root/r['frame_image']
            if sha(p)!=r['frame_image_sha256']:raise ValueError('Changed picture')
            target=f'{name}-{f}.png';shutil.copyfile(p,out/target);sources[str(p)]=sha(p)
            body+=f'<figure><img src="{target}"><figcaption>{name}</figcaption></figure>'
        body+='</div>'
    body+='<p>No release verdict: graphics deadlines, full-route palette freshness, heavy-combat speed and audio remain separate checks. <a href="report.json">Every color difference, source equality and hashes</a> · <a href="../progress-3728/">Progress</a> · <a href="https://github.com/struktured-labs/river-city-ransom-snes/issues/18">Issue18</a></p>'
    (out/'index.html').write_text(body)
    sources[str(Path(__file__))]=sha(Path(__file__))
    report['artifacts']={p.name:sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:dict(counts=v['counts'],no_observed_stage_regression=v['no_observed_stage_regression']) for k,v in comparisons.items()}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ('baseline','prior','trial','out'):parser.add_argument('--'+k,type=Path,required=True)
    audit(**vars(parser.parse_args()))
