"""Exact cross-ROM composition guard for fused PPU + cheaper queued ring reads."""
import argparse
import json
from pathlib import Path

from tools import queued_vblank_replay as base
from tools.build_queued_read_poll import build as queued
from tools.build_ppu_fusion_trial import build as fuse
from tools.benchmark_report import sha


def replay(**args):
    original_build, original_guard = base.build, base.guarded_variant
    def build(parent,out):
        intermediate = out.parent/'fusion'
        fuse(parent,intermediate)
        queued(intermediate,out)
    def guard(parent,trial,variant,snapshot_pc):
        low = snapshot_pc&65535
        if 0x6000<=low<0x7100 or 0x7b00<=low<0x7c00:
            raise ValueError('Checkpoint in changed fusion/producer guard')
        result = original_guard(parent,trial,variant,snapshot_pc)
        result['read_poll'] = True
        return result
    base.build, base.guarded_variant = build, guard
    try:
        passed = base.replay(**args)
    finally:
        base.build, base.guarded_variant = original_build, original_guard
    path = args['out']/'report.json'
    report = json.loads(path.read_text())
    files = [Path(__file__),Path('tools/build_queued_read_poll.py'),
        Path('tools/build_queued_vblank_fast.py'),Path('tools/build_ppu_fusion_trial.py'),
        Path('snes/ppu_stub_fusion.asm'),Path('snes/ppu_register_fast.cfg'),Path('tools/build_native.py'),
        args['trial']/'queued-read-poll.asm',args['trial']/'retained-guard.bin',
        args['trial']/'ppu-fusion.bin',args['trial']/'ppu-fusion.lbl']
    report['sources'].update({str(p):sha(p) for p in files})
    path.write_text(json.dumps(report,indent=2)+'\n')
    return passed


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('core','candidate','normal','checkpoint-report','out','trial','resume-control'):
        parser.add_argument('--'+key,type=Path,required=True)
    for key in ('frame','frames'):
        parser.add_argument('--'+key,type=int,required=True)
    raise SystemExit(0 if replay(**vars(parser.parse_args())) else 1)
