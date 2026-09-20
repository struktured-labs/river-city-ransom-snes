"""Reuse the executed state/ownership oracle for the explicit delay13 variant."""
import argparse
import json
from pathlib import Path

from tools import check_interleaved_volume_state as oracle
from tools.benchmark_report import sha
from tools.build_guarded_volume_delay import patch


def check(core,parent,baseline,trial,out):
    pair=out.with_name(out.name+'-fixtures')
    if pair.exists() or out.exists():raise ValueError('Fresh qualification required')
    pair.mkdir();(pair/'baseline').symlink_to(baseline.resolve(),target_is_directory=True)
    (pair/'trial').symlink_to(trial.resolve(),target_is_directory=True)
    old=oracle.patch
    try:
        oracle.patch=patch
        oracle.check(core,parent,pair,out)
    finally:oracle.patch=old
    report=json.loads((out/'report.json').read_text())
    report['sources'].update({str(p):sha(p) for p in (Path(__file__),Path('tools/build_guarded_volume_delay.py'),Path('tests/test_guarded_volume_delay.py'))})
    report['patch_override']='tools.build_guarded_volume_delay.patch'
    report['scope']=__doc__+' '+report['scope']
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','parent','baseline','trial','out'):p.add_argument('--'+name,type=Path,required=True)
    check(**vars(p.parse_args()))
