"""Exact fusion plus both-stride dirty-cache composition, using the proven guard."""
import argparse
import json
from pathlib import Path

from tools import ppu_fusion_replay as base
from tools.build_ring_dirty_trial import build as dirty_build
from tools.benchmark_report import sha

ORIGINAL_GUARD = base.guarded_variant


def guarded_variant(parent,trial,variant,snapshot_pc):
    # The base guard covers $6000..$70FF, including the larger $6900..$6AFF
    # helper, and reconstructs the complete ROM. Substitute the recipe only.
    if variant != 'fusion-tile':
        raise ValueError('Wrong base composition')
    previous = base.build_tile
    base.build_tile = dirty_build
    try:
        record = ORIGINAL_GUARD(parent,trial,variant,snapshot_pc)
    finally:
        base.build_tile = previous
    record['variant'] = 'fusion-dirty'
    return record


def replay(**args):
    previous = base.guarded_variant
    base.guarded_variant = guarded_variant
    try:
        passed = base.replay(**args,variant='fusion-tile')
    finally:
        base.guarded_variant = previous
    path = args['out']/'report.json'
    report = json.loads(path.read_text())
    files = [Path(__file__),Path('tools/build_ring_dirty_trial.py'),
             Path('snes/ring_dirty_cache.asm'),Path('snes/ring_dirty_cache.cfg')]
    report['sources'].update({str(p):sha(p) for p in files})
    report['composition'] = 'PPU stub fusion plus both-stride ring dirty cache'
    path.write_text(json.dumps(report,indent=2)+'\n')
    return passed


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('core','candidate','normal','checkpoint-report','out','trial','resume-control'):
        p.add_argument('--'+name,type=Path,required=True)
    for name in ('frame','frames'):
        p.add_argument('--'+name,type=int,required=True)
    raise SystemExit(0 if replay(**vars(p.parse_args())) else 1)
