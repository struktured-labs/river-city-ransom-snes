"""Execute unchanged continuous-clock/ownership guards for the command-priority ablation."""
import argparse
import json
from pathlib import Path
import tempfile
from tools import check_receiver_token_priority as harness
from tools.build_receiver_token_only import patch
from tools.benchmark_report import sha

def check(parent,candidate,core,out):
    if out.exists():raise ValueError('Fresh output required')
    previous=harness.patch
    try:
        harness.patch=patch
        with tempfile.TemporaryDirectory(prefix='rcr-token-only-') as tmp:
            scratch=Path(tmp)/'proof'
            try:harness.check(parent,candidate,core,scratch)
            except ValueError:
                if not (scratch/'report.json').exists():raise
            report=json.loads((scratch/'report.json').read_text())
    finally:harness.patch=previous
    for p in (Path(__file__),Path('tools/build_receiver_token_only.py')):report['sources'][str(p)]=sha(p)
    report['scope']=__doc__
    out.mkdir();(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'])))
    if not report['passed']:raise ValueError('SPC regression')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','candidate','core','out'):p.add_argument('--'+k,type=Path,required=True)
    check(**vars(p.parse_args()))
