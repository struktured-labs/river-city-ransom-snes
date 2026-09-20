"""Reuse exact-state row replay, admitting only the bound full-scan/deadline composition."""
import argparse
import json
from pathlib import Path
import tempfile

from tools import replay_row_scan_checkpoint as base
from tools.benchmark_report import sha
from tools.build_bounded_row_scan import build, patch


def replay(**args):
    trial = args['trial']
    with tempfile.TemporaryDirectory(prefix='rcr-bounded-scan-verify-') as directory:
        fresh = Path(directory)/'candidate'
        build(args['candidate'], fresh)
        for name in ('native-cpu.sfc','publisher-scan.bin','publisher-scan.lbl'):
            if (fresh/name).read_bytes() != (trial/name).read_bytes():
                raise ValueError('Changed bounded-scan composition')
    original = base.patch
    def guarded(image):
        result = patch(image, (trial/'publisher-scan.bin').read_bytes())
        return result, [i for i, (a,b) in enumerate(zip(image, result)) if a != b]
    try:
        base.patch = guarded
        passed = base.replay(**args)
    finally:
        base.patch = original
    p = args['out']/'report.json'
    r = json.loads(p.read_text())
    r['scope'] = (__doc__+' Fresh assembly must reproduce complete trial ROM and helper. '
        'Same-ROM control must exactly reproduce uninterrupted video/state/input/native PCM. '
        'Identical initial full WRAM/VRAM and all CPU registers; later differences retained. '
        'No restored observer clocks used; no equality or release claim for the trial.')
    meta = json.loads((trial/'manifest.json').read_text())
    r['sources'].update(meta['experimental_bounded_full_scan']['sources'])
    r['sources'].update({str(p): sha(p) for p in (Path(__file__), Path('tools/build_bounded_row_scan.py'))})
    r['row_scan_trial']['bounded_by_row_room'] = True
    p.write_text(json.dumps(r, indent=2)+'\n')
    return passed


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for k in ('core','candidate','normal','checkpoint-report','out','trial','resume-control'):
        p.add_argument('--'+k, type=Path, required=True)
    for k in ('frame','frames'):
        p.add_argument('--'+k, type=int, required=True)
    raise SystemExit(0 if replay(**vars(p.parse_args())) else 1)
