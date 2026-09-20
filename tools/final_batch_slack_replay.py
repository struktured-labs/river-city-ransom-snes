"""Exact rebuilt final-batch slack at the first hardware-entry instruction."""
import argparse
import json
from pathlib import Path

from tools import owned_queue_priority_replay as base
from tools.build_final_batch_slack import build
from tools.benchmark_report import sha


def replay(**args):
    original=base.build;base.build=build
    try:passed=base.replay(**args)
    finally:base.build=original
    p=args['out']/'report.json';r=json.loads(p.read_text())
    r['sources'].update({str(p):sha(p) for p in (Path(__file__),Path('tools/build_final_batch_slack.py'))})
    p.write_text(json.dumps(r,indent=2)+'\n');return passed


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('core','candidate','normal','checkpoint-report','out','trial','resume-control'):
        p.add_argument('--'+k,type=Path,required=True)
    for k in ('frame','frames'):p.add_argument('--'+k,type=int,required=True)
    raise SystemExit(0 if replay(**vars(p.parse_args())) else 1)
