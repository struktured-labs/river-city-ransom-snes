"""Run the existing executed state/validity/timer oracle on the tail variant.

Only the expected patch function is substituted; all cases, DSP/DP comparison
rules, mutant, receiver checks and clock measurement remain unchanged. The
wrapper records the substitution and binds its source explicitly.
"""
import argparse
import json
from pathlib import Path

from tools import check_balanced_startup_game as oracle
from tools.benchmark_report import sha
from tools.build_tail_startup_pitch import patch


def check(core, parent, candidate, out):
    if out.exists(): raise ValueError('Fresh qualification required')
    paths = (Path(__file__), Path('tools/build_tail_startup_pitch.py'),
             Path('tests/test_tail_startup_pitch.py'))
    sources = {str(p): sha(p) for p in paths}
    old = oracle.patch
    try:
        oracle.patch = patch
        oracle.check(core, parent, candidate, out)
    finally:
        oracle.patch = old
    report = json.loads((out/'report.json').read_text())
    if any(sha(Path(p)) != h for p, h in sources.items()):
        raise ValueError('Changed tail oracle source')
    report['sources'].update(sources)
    report['expected_patch_override'] = 'tools.build_tail_startup_pitch.patch'
    report['scope'] = __doc__+' '+report['scope']
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('core', 'parent', 'candidate', 'out'): p.add_argument('--'+name, type=Path, required=True)
    check(**vars(p.parse_args()))
