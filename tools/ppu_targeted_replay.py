"""Use the exact targeted-PPU rebuilding recipe in the full-ROM replay guard."""
import argparse
import json
from pathlib import Path

from tools import ppu_register_replay as engine
from tools.build_ppu_targeted_trial import build
from tools.benchmark_report import sha


def replay(**args):
    original = engine.build
    engine.build = build
    try:
        passed = engine.replay(**args)
    finally:
        engine.build = original
    path = args['out']/'report.json'
    report = json.loads(path.read_text())
    sources = [Path(__file__),Path('tools/build_ppu_targeted_trial.py')]
    report['sources'].update({str(p):sha(p) for p in sources})
    report['ppu_targeted'] = True
    path.write_text(json.dumps(report,indent=2)+'\n')
    return passed


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('core','candidate','normal','checkpoint-report','out'):
        p.add_argument('--'+name,type=Path,required=True)
    for name in ('frame','frames'):
        p.add_argument('--'+name,type=int,required=True)
    for name in ('trial','resume-control'):
        p.add_argument('--'+name,type=Path)
    p.add_argument('--variant',choices=('ppu','ppu-tile'),default='ppu')
    raise SystemExit(0 if replay(**vars(p.parse_args())) else 1)
