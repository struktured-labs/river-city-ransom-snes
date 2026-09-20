"""Exact composition of stub fusion then queued VBlank collection."""
import argparse
import json
from pathlib import Path

from tools import queued_vblank_replay as base
from tools.build_ppu_fusion_trial import build as fusion
from tools.build_queued_vblank_trial import build as queue
from tools.benchmark_report import sha

ORIGINAL_GUARD=base.guarded_variant


def build(parent,out):
    intermediate=out.parent/'fusion'
    fusion(parent,intermediate)
    queue(intermediate,out)


def guarded_variant(parent,trial,variant,snapshot_pc):
    if 0x6000<=snapshot_pc&65535<0x7100:
        raise ValueError('Checkpoint in changed fusion caller/helper')
    previous=base.build;base.build=build
    try:result=ORIGINAL_GUARD(parent,trial,variant,snapshot_pc)
    finally:base.build=previous
    result['variant']='queued-vblank-fusion'
    return result


def replay(**args):
    previous=base.guarded_variant;base.guarded_variant=guarded_variant
    try:passed=base.replay(**args)
    finally:base.guarded_variant=previous
    path=args['out']/'report.json';r=json.loads(path.read_text())
    files=[Path(__file__),Path('tools/build_ppu_fusion_trial.py'),Path('tools/build_native.py'),
           Path('snes/ppu_stub_fusion.asm'),Path('snes/ppu_register_fast.cfg'),
           args['trial']/'ppu-fusion.bin',args['trial']/'ppu-fusion.lbl']
    r['sources'].update({str(p):sha(p) for p in files})
    path.write_text(json.dumps(r,indent=2)+'\n')
    return passed


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','candidate','normal','checkpoint-report','out','trial','resume-control'):
        p.add_argument('--'+name,type=Path,required=True)
    for name in ('frame','frames'):p.add_argument('--'+name,type=int,required=True)
    raise SystemExit(0 if replay(**vars(p.parse_args())) else 1)
