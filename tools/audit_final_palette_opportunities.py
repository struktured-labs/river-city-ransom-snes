"""Retain early-OAM publications without a same-frame final palette batch; diagnostic only."""
import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path
from tools.audit_main_display_latency import bound_report
from tools.audit_dma_safety import parse
from tools.benchmark_report import sha


def audit(before,after,out):
    if out.exists():raise ValueError('Fresh output required')
    sources={};runs={}
    for name,root in (('before',before),('after',after)):
        proof=root/'dma-capture.json';r=bound_report(proof)
        if not r['observer_neutral']:raise ValueError('Need neutral DMA observation')
        sources.update(r['sources']);sources[str(proof)]=sha(proof)
        with Path(r['trace']).open() as stream:events=parse(csv.reader(stream))
        groups=defaultdict(list)
        for e in events:groups[(e['start_frame'],e['native_id'])].append(e)
        missing=[];all_frames=[]
        for key,es in groups.items():
            oam=[e for e in es if e['target']==4 and e['source']==0x7e5000 and
                 e['count']==544 and e['classification']=='vblank']
            if not oam:continue
            all_frames.append(key)
            if not any(e['target']==0x22 and e['source']==0x7e5400 and e['count']==32 for e in es):
                missing.append(dict(frame=key[0],native_id=key[1],oam=oam,
                                    transfers=es))
        runs[name]=dict(visible_early_oam_groups=len(all_frames),
                       groups_without_final_palette=len(missing),records=missing)
    sources[str(Path(__file__))]=sha(Path(__file__))
    sources['tools/audit_dma_safety.py']=sha('tools/audit_dma_safety.py')
    report=dict(sources=sources,runs=runs,release_ready=False,
                scope=__doc__+' A missing batch is not itself a changed-palette lag: source generation '
                'and actual CGRAM freshness are not observed here. No timing alignment across '
                'cartridges. Keep every missing group; this is neither a liveness pass nor a waiver.')
    out.mkdir(parents=True);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:{f:v[f] for f in ('visible_early_oam_groups','groups_without_final_palette')}
                      for k,v in runs.items()}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ('before','after','out'):parser.add_argument('--'+k,type=Path,required=True)
    audit(**vars(parser.parse_args()))
