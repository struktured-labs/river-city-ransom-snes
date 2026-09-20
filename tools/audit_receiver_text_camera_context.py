"""Correct3952 gallery wording and include unchanged picture5979 with camera context."""
import argparse
import json
from pathlib import Path
import shutil
from tools.audit_receiver_text_deadlines import audit
from tools.benchmark_report import sha


def review(**kwargs):
    # Preserve3952 and its source bindings. Generate a fresh corrected report.
    audit(**kwargs)
    out=kwargs['out']; report=json.loads((out/'report.json').read_text())
    context={}
    body=(out/'index.html').read_text()
    old='All full-route changed pictures follow, including frame5979\'s unresolved logical-camera\nsample.'
    if old not in body:
        raise ValueError('Changed gallery template')
    body=body.replace(old,'All48 full-route changed pictures follow. Frame5979 is separately included\nbelow: its rendered pictures match despite the unresolved logical-camera sample.')
    body+='<h2>Frame5979: equal rendered pictures, different logical-camera sample</h2><div class="pair">'
    for arm,key in (('before','parent_normal'),('after','trial_normal')):
        root=kwargs[key]; rows=json.loads((root/'timeline.json').read_text());row=rows[5978]
        if row['frame']!=5979:
            raise ValueError('Wrong context frame')
        p=root/row['frame_image']
        if sha(p)!=row['frame_image_sha256']:
            raise ValueError('Changed context image')
        context[arm]=dict(frame=5979,video_sha256=row['video_sha256'],native=row['native'])
        name=f'{arm}-5979.png';shutil.copyfile(p,out/name);report['sources'][str(p)]=sha(p)
        body+=f'<img src="{name}" alt="{arm} frame5979">'
    if context['before']['video_sha256']!=context['after']['video_sha256']:
        raise ValueError('Context no longer has equal pictures')
    body+='</div><p>Equal pictures do not establish why the original camera RAM briefly differs.</p>'
    (out/'index.html').write_text(body)
    report['context_5979']=context
    report['presentation_correction']='3952 claimed5979 was among changed pictures; it is not. Included separately here.'
    report['sources'][str(Path(__file__))]=sha(Path(__file__))
    report['artifacts']={p.name:sha(p) for p in out.iterdir() if p.name!='report.json'}
    if any(sha(Path(p))!=h for p,h in report['sources'].items()):
        raise ValueError('Changed source')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ('before','after','parent_trace','trial_trace','parent_normal','trial_normal','out'):
        parser.add_argument('--'+k.replace('_','-'),type=Path,required=True)
    review(**vars(parser.parse_args()))
