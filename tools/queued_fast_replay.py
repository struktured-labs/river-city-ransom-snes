"""Guard exact fast-poll/queued-priority compositions, optionally with stub fusion."""
import argparse
import json
from pathlib import Path

from tools import queued_vblank_replay as base
from tools.build_queued_vblank_fast import build as fast
from tools.build_ppu_fusion_trial import build as fuse
from tools.benchmark_report import sha


def replay(defer_pending=False,fusion=False,**args):
    original_guard,original_build=base.guarded_variant,base.build
    def build(parent,out):
        source=parent
        if fusion:
            source=out.parent/'fusion';fuse(parent,source)
        fast(source,out,defer_pending)
    def guard(parent,trial,variant,snapshot_pc):
        low=snapshot_pc&65535
        if defer_pending and 0x7b00<=low<0x7c00 or fusion and 0x6000<=low<0x7100:
            raise ValueError('Checkpoint inside changed guard/fusion path')
        result=original_guard(parent,trial,variant,snapshot_pc)
        result.update(fast_poll=True,defer_pending=defer_pending,fusion=fusion)
        return result
    base.build=build;base.guarded_variant=guard
    try:passed=base.replay(**args)
    finally:base.build=original_build;base.guarded_variant=original_guard
    path=args['out']/'report.json';record=json.loads(path.read_text())
    files=[Path(__file__),Path('tools/build_queued_vblank_fast.py'),args['trial']/'queued-vblank-fast.asm',
           args['trial']/'retained-guard.bin']
    if fusion:files += [Path('tools/build_ppu_fusion_trial.py'),Path('snes/ppu_stub_fusion.asm'),
                       Path('snes/ppu_register_fast.cfg'),Path('tools/build_native.py'),
                       args['trial']/'ppu-fusion.bin',args['trial']/'ppu-fusion.lbl']
    record['sources'].update({str(p):sha(p) for p in files})
    path.write_text(json.dumps(record,indent=2)+'\n')
    return passed


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','candidate','normal','checkpoint-report','out','trial','resume-control'):
        p.add_argument('--'+name,type=Path,required=True)
    for name in ('frame','frames'):p.add_argument('--'+name,type=int,required=True)
    p.add_argument('--defer-pending',action='store_true');p.add_argument('--fusion',action='store_true')
    raise SystemExit(0 if replay(**vars(p.parse_args())) else 1)
