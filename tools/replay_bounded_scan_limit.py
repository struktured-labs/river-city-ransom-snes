"""Replay a pinned bounded-scan-limit variant against the original encounter state."""
import argparse
import json
from pathlib import Path

from tools import replay_row_scan_checkpoint as base
from tools.benchmark_report import sha
from tools.build_bounded_row_scan import patch as bounded
from tools.build_bounded_scan_limit import patch as limit_patch


def replay(**args):
    trial = args['trial']; spec = json.loads((trial/'manifest.json').read_text())['bounded_scan_limit']
    if any(sha(Path(p)) != h for p,h in spec['sources'].items()):
        raise ValueError('Changed limit dependencies')
    original = base.patch
    def guarded(image):
        # limit_patch pins the complete intermediate ROM, including helper
        # bytes, so an unrelated helper/code mutation cannot be admitted.
        data = limit_patch(bounded(image, (trial/'publisher-scan.bin').read_bytes()), spec['limit'])
        return data, [i for i,(a,b) in enumerate(zip(image,data)) if a != b]
    try:
        base.patch = guarded
        passed = base.replay(**args)
    finally:
        base.patch = original
    p = args['out']/'report.json'; r = json.loads(p.read_text())
    r['row_scan_trial'].update(after=spec['limit'], bounded_by_row_room=True)
    r['sources'].update(spec['sources'])
    r['sources'].update({str(p):sha(p) for p in (Path(__file__), Path('tools/build_bounded_row_scan.py'),
                                             Path('tools/build_bounded_scan_limit.py'))})
    r['scope'] = (__doc__+' Exact intermediate-ROM hash guards helper and all non-limit bytes. '
        'Same-ROM video/state/input/native-PCM control and all initial CPU/WRAM/VRAM equality required. '
        'All later differences retained; not a trial equality or release verdict.')
    p.write_text(json.dumps(r, indent=2)+'\n')
    return passed


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for k in ('core','candidate','normal','checkpoint-report','out','trial','resume-control'):
        p.add_argument('--'+k, type=Path, required=True)
    for k in ('frame','frames'): p.add_argument('--'+k, type=int, required=True)
    raise SystemExit(0 if replay(**vars(p.parse_args())) else 1)
