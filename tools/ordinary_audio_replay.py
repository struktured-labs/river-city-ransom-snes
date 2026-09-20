"""Exact rebuilt ordinary-early audio at the first hardware-entry instruction."""
import argparse
import json
from pathlib import Path
import tempfile

from tools import owned_queue_priority_replay as base
from tools.build_final_batch_slack import build as final_batch
from tools.build_ordinary_early_audio import build as ordinary
from tools.benchmark_report import sha


def compose(parent,out):
    with tempfile.TemporaryDirectory(prefix='rcr-ordinary-audio-rebuild-') as directory:
        intermediate=Path(directory)/'final-batch'
        final_batch(parent,intermediate)
        ordinary(intermediate,out)


def replay(**args):
    original=base.build;base.build=compose
    try:passed=base.replay(**args)
    finally:base.build=original
    p=args['out']/'report.json';r=json.loads(p.read_text())
    files=(Path(__file__),Path('tools/build_final_batch_slack.py'),Path('tools/build_ordinary_early_audio.py'),
           args['trial']/'ordinary-audio.bin',args['trial']/'ordinary-audio.lbl')
    r['sources'].update({str(p):sha(p) for p in files})
    p.write_text(json.dumps(r,indent=2)+'\n');return passed


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('core','candidate','normal','checkpoint-report','out','trial','resume-control'):
        p.add_argument('--'+k,type=Path,required=True)
    for k in ('frame','frames'):p.add_argument('--'+k,type=int,required=True)
    raise SystemExit(0 if replay(**vars(p.parse_args())) else 1)
