"""Byte-rebuilt post-DMA deadline composition at the exact hardware-entry boundary."""
import argparse
import json
from pathlib import Path

from tools import owned_queue_priority_replay as base
from tools.build_publisher_postdma_deadline import build
from tools.benchmark_report import sha


def replay(**args):
    original=base.build;base.build=build
    try:passed=base.replay(**args)
    finally:base.build=original
    p=args['out']/'report.json';r=json.loads(p.read_text())
    files=[Path(__file__),Path('tools/build_publisher_postdma_deadline.py'),
        Path('snes/publisher_postdma_deadline.asm'),Path('snes/publisher_scan_deadline.cfg'),
        args['trial']/'publisher-postdma.bin',args['trial']/'publisher-postdma.lbl']
    r['sources'].update({str(p):sha(p) for p in files});p.write_text(json.dumps(r,indent=2)+'\n')
    return passed


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('core','candidate','normal','checkpoint-report','out','trial','resume-control'):
        p.add_argument('--'+k,type=Path,required=True)
    for k in ('frame','frames'):p.add_argument('--'+k,type=int,required=True)
    raise SystemExit(0 if replay(**vars(p.parse_args())) else 1)
