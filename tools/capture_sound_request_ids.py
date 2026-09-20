"""Observe actual request ID in X immediately after the original LDX $07FF."""
import argparse
import json
from pathlib import Path
from tools import capture_sound_busy as base
from tools.benchmark_report import sha

def capture(candidate,core,normal,out):
    source=Path(__file__);digest=sha(source)
    points,guards=base.POINTS,base.GUARDS
    try:
        base.POINTS=(0x8146,0x814b,0x819a,0x802f)
        base.GUARDS=dict(guards,**{})
        base.GUARDS[0x802c]='aeff07f0181060'
        base.capture(candidate,core,normal,out)
    finally:base.POINTS,base.GUARDS=points,guards
    if sha(source)!=digest:raise ValueError('Changed wrapper')
    proof=out/'sound-busy.json'
    report=json.loads(proof.read_text())
    report['sources'].update({str(source):digest,str(proof):sha(proof)})
    report['scope']=__doc__
    (out/'sound-request-ids.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('candidate','core','normal','out'):p.add_argument('--'+k,type=Path,required=True)
    capture(**vars(p.parse_args()))
