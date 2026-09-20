"""Guard exact retained-entry + active-scanout wait composition on state restore."""
import argparse
import json
from pathlib import Path

from tools import retained_entry_replay as base
from tools.build_retained_wait import build
from tools.benchmark_report import sha
from tools.build_retained_producer_guard import symbols


def replay(**args):
    original_build,original_guard=base.build,base.guarded_variant
    def guard(parent,trial,variant,snapshot_pc):
        boot=symbols(parent/'native_boot.lbl');low=snapshot_pc&65535
        if snapshot_pc>>16 in (0,0xc0) and boot['@deferred_late_vblank']<=low<boot['@deferred_late_vblank']+6:
            raise ValueError('Checkpoint inside changed beam wait')
        return original_guard(parent,trial,variant,snapshot_pc)
    base.build,base.guarded_variant=build,guard
    try:passed=base.replay(**args)
    finally:base.build,base.guarded_variant=original_build,original_guard
    path=args['out']/'report.json';r=json.loads(path.read_text())
    r['sources'].update({str(p):sha(p) for p in (Path(__file__),Path('tools/build_retained_wait.py'),
        args['trial']/'retained-wait.asm')})
    path.write_text(json.dumps(r,indent=2)+'\n')
    return passed


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ('core','candidate','normal','checkpoint-report','out','trial','resume-control'):
        parser.add_argument('--'+k,type=Path,required=True)
    for k in ('frame','frames'):parser.add_argument('--'+k,type=int,required=True)
    raise SystemExit(0 if replay(**vars(parser.parse_args())) else 1)
