"""Same-state ring replay using a fresh exact stride32-only tile-cache rebuild."""
import argparse
import json
from pathlib import Path

from tools import ring_dirty_replay as engine
from tools.build_ring_tile_trial import build
from tools.benchmark_report import sha


def replay(**args):
    # The shared guard still compares complete ROM/helper bytes, unchanged
    # labels and all initial state. Its512-byte PC exclusion conservatively
    # contains this256-byte helper. Replace only the exact rebuilding recipe.
    original = engine.build
    engine.build = build
    try:
        passed = engine.replay(**args)
    finally:
        engine.build = original
    report_path = args['out']/'report.json'
    report = json.loads(report_path.read_text())
    paths = [Path(__file__),Path('tools/build_ring_tile_trial.py'),Path('snes/ring_tile_cache.asm'),
             Path('snes/ring_stride_cache.asm'),Path('snes/ring_stride_cache.cfg'),
             Path('tools/build_ring_stride_trial.py')]
    report['sources'].update({str(p):sha(p) for p in paths})
    report['ring_cache_variant'] = 'stride32-only'
    report_path.write_text(json.dumps(report,indent=2)+'\n')
    return passed


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('core','candidate','normal','checkpoint-report','out'):
        p.add_argument('--'+name,type=Path,required=True)
    for name in ('frame','frames'):
        p.add_argument('--'+name,type=int,required=True)
    for name in ('trial','resume-control'):
        p.add_argument('--'+name,type=Path)
    raise SystemExit(0 if replay(**vars(p.parse_args())) else 1)
