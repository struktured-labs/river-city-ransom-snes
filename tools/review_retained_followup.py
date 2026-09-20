"""Expose the earlier replay's picture-gate failure alongside retained-service progress."""
import argparse
import html
import json
from pathlib import Path
import shutil

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.frame_audit import verify_frame
from tools.review_retained_producer import authenticated_replay,compare


def review(candidate,control,trial,service,combat,out):
    if out.exists():raise ValueError('Fresh output required')
    sources={}
    proofs={}
    for name,root in (('service',service),('combat',combat)):
        p=root/'report.json';r=bound_report(p)
        if r['sources'].get(str(candidate/'native-cpu.sfc'))!=sha(candidate/'native-cpu.sfc'):
            raise ValueError('Different candidate proof')
        for file,digest in r.get('artifacts',{}).items():
            if sha(root/file)!=digest:raise ValueError('Changed review artifact')
        sources.update(r['sources']);sources[str(p)]=sha(p);proofs[name]=r
    before,old=authenticated_replay(control);after,new=authenticated_replay(trial)
    if (not before['passed'] or not after['cross_rom_restore_verified'] or
            after['trial']['resume_control']!=str(control) or
            after['trial']['trial_rom_sha256']!=sha(candidate/'native-cpu.sfc') or
            (control/'initial.ram').read_bytes()!=(trial/'initial.ram').read_bytes()):
        raise ValueError('Invalid earlier exact-state replay')
    comparison=compare(old,new,2239)
    out.mkdir(parents=True);cards=[]
    for name,root,r,rows in (('parent',control,before,old),('candidate',trial,after,new)):
        sources.update(r['sources']);sources[str(root/'report.json')]=sha(root/'report.json')
        for row in rows:
            if not 2237<=row['frame']<=2241:continue
            source=verify_frame(root,row);target=f'{name}-{row["frame"]}.png'
            shutil.copy2(source,out/target);sources[str(source)]=sha(source)
            cards.append(f'<figure><img src="{target}"><figcaption>{name} · {row["frame"]}</figcaption></figure>')
    paths=[Path(__file__),Path('tools/review_retained_producer.py'),Path('tools/frame_audit.py')]
    sources.update({str(p):sha(p) for p in paths})
    report=dict(earlier_replay=comparison,proofs=proofs,sources=sources,release_ready=False,
        physical_verified=False,pop_free_verified=False,scope=__doc__+
        ' Do not waive the earlier fixed-picture gate because its timing counters improved.')
    speed=proofs['combat']['including_busy']['frame_histogram']
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Retained scheduler follow-up</title>'
        '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1200px;margin:2em auto}'
        'a{color:cyan}.grid{display:grid;grid-template-columns:repeat(5,1fr);gap:8px}'
        'figure{margin:0}img{width:100%;image-rendering:pixelated}pre{white-space:pre-wrap}</style>'
        '<h1>Retained-event fix: useful progress, still not deployable</h1>'
        '<p>Candidate2971 remains offline. Rivalmage is occupied and untouched; Bluemage is the next '
        'permitted hardware target, once regressions are resolved.</p>'
        '<ul><li>The newer saved-state failure completes one update earlier, with all seven original bodies '
        'and seven ordered audio packets.</li><li>Full9248-frame traversal: no split/stale-camera failures; '
        'zero short irregular park holds in either direction.</li><li>Fresh combat still fails: '+html.escape(str(speed))+
        ' start-interval histogram.</li><li>The earlier2239 replay keeps its recovered counters, but pictures '
        'differ at2238 and2239. That fixed-picture gate FAILS; the cause is not yet qualified.</li></ul>'
        '<h2>Earlier saved-state replay: parent and candidate</h2><div class="grid">'+''.join(cards)+'</div>'
        '<h2>All earlier recovery gates</h2><pre>'+html.escape(json.dumps(comparison['gates'],indent=2))+'</pre>'
        '<p><a href="../'+service.name+'/">Newer event-ownership replay, failed first attempt and native audio</a></p>'
        '<p>Audio transport and visual tests here do not establish pop-free sound, original-NES-speed parity, '
        'new menu regression coverage or physical qualification.</p>'
        '<p><a href="report.json">Source-bound proofs, all failures and limits</a></p>')
    report['artifacts']={p.name:sha(p) for p in out.iterdir() if p.is_file()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(earlier_gates=comparison['gates'],sources=len(sources),artifacts=len(report['artifacts']))))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ('candidate','control','trial','service','combat','out'):
        parser.add_argument('--'+k,type=Path,required=True)
    review(**vars(parser.parse_args()))
