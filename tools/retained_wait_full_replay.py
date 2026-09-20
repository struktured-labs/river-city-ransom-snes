"""Rebuild the entire fusion/queue/retained-entry composition for the earlier saved-state stall."""
import argparse
import json
from pathlib import Path

from tools import queued_read_poll_replay as base
from tools.build_queued_read_poll import build as poll
from tools.build_retained_wait import build as retained
from tools.benchmark_report import sha
from tools.build_retained_producer_guard import symbols


def replay(**args):
    checkpoints=json.loads(args['checkpoint_report'].read_text())
    states=[r for r in checkpoints['checkpoints'] if r['frame']==args['frame']]
    if len(states)!=1 or states[0]['registers']['pc']!=symbols(args['candidate']/'native_boot.lbl')['nmi']:
        raise ValueError('This combined replay requires an exact hardware-entry boundary')
    original=base.queued
    def build(parent,out):
        intermediate=out.parent/'read-poll';poll(parent,intermediate);retained(intermediate,out)
    base.queued=build
    try:passed=base.replay(**args)
    finally:base.queued=original
    path=args['out']/'report.json';r=json.loads(path.read_text())
    files=[Path(__file__),Path('tools/build_retained_wait.py'),Path('tools/build_retained_entry.py'),
        Path('snes/retained_entry.asm'),Path('snes/retained_entry.cfg'),args['trial']/'retained-wait.asm',
        args['trial']/'retained-entry.bin',args['trial']/'retained-entry.lbl']
    r['sources'].update({str(p):sha(p) for p in files})
    path.write_text(json.dumps(r,indent=2)+'\n')
    return passed


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ('core','candidate','normal','checkpoint-report','out','trial','resume-control'):
        parser.add_argument('--'+k,type=Path,required=True)
    for k in ('frame','frames'):parser.add_argument('--'+k,type=int,required=True)
    raise SystemExit(0 if replay(**vars(parser.parse_args())) else 1)
