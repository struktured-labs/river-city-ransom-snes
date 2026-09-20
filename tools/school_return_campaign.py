"""Input-only school -> alley -> school reference, identical policy on NES/SNES."""
import argparse
from contextlib import contextmanager
from copy import deepcopy
import json
import os
from pathlib import Path
import sys

from tools import benchmark_capture as benchmark
from tools.benchmark_report import sha, verify_capture
from tools.traversal_waypoints import cursor_mask, state

NAME='traversal-school-return'
SOURCE_FILES=(Path('tools/traversal_waypoints.py'),)


def reached(kind,ram,cursor=()):
    if kind not in ('school-to-alley','alley-to-school'):
        raise ValueError('Unknown school-return waypoint')
    s=state(ram)
    return (s['room']==(1 if kind=='school-to-alley' else 0) and s['task']==0xc0
            and not s['menu']&0x80 and not s['pause']&0x20)


def buttons(kind,ram,offset,cursor=()):
    if reached(kind,ram,cursor):return []
    s=state(ram)
    if s['task']!=0xc0 or s['menu']&0x80 or s['pause']&0x20:return []
    if s['room']!=(0 if kind=='school-to-alley' else 1):return []
    return ['Right' if kind=='school-to-alley' else 'Left']+(['A','B'] if offset%30<4 else [])


def validate_completion(kind,samples,limit,matched,cursors=None):
    streak=0;first=None
    for i,ram in enumerate(samples):
        streak=streak+1 if reached(kind,ram) else 0
        if streak==3 and first is None:first=i+1
    if (matched and first!=len(samples)) or (not matched and (first is not None or len(samples)!=limit)):
        raise ValueError('Waypoint did not stop at first stable completion or true timeout')


@contextmanager
def installed():
    original=benchmark.scenario_for;old_policy=benchmark.waypoint_policy
    prefix=deepcopy(original('traversal-park-single-sweep'))
    prefix=prefix[:next(i for i,p in enumerate(prefix) if p['name']=='right_00')]
    phases=prefix+[dict(name='reach_alley',waypoint='school-to-alley',frames=3600),
        dict(name='alley_settle',frames=120),
        dict(name='return_school',waypoint='alley-to-school',frames=3600),
        dict(name='school_settle',frames=240)]
    benchmark.scenario_for=lambda name:deepcopy(phases) if name==NAME else original(name)
    benchmark.waypoint_policy=lambda name:sys.modules[__name__] if name==NAME else old_policy(name)
    try:yield
    finally:
        benchmark.scenario_for=original;benchmark.waypoint_policy=old_policy


def capture(system,core,candidate,out):
    if out.exists() or any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Fresh output and no inherited observer overrides required')
    rom=candidate/'native-cpu.sfc' if system=='snes' else Path('roms/river-city-ransom-us.nes')
    paths=[Path(__file__),Path('tools/traversal_waypoints.py'),Path('tools/benchmark_capture.py'),
        Path('tools/smoke_libretro.py'),core,rom]
    if system=='snes':paths.append(candidate/'manifest.json')
    sources={str(p):sha(p) for p in paths}
    refs={'menu':(Path('build/reference-title-05'),600),'settings':(Path('build/reference-walk-02'),600),
          'story':(Path('build/reference-walk-02'),900),'street':(Path('build/reference-walk-02'),1800)}
    with installed():
        benchmark.capture(core,rom,system,refs,out,NAME,True,True,system=='nes')
        receipt,rows=verify_capture(out)
    if not receipt['capture_complete'] or any(r['fault'] for r in rows):
        raise ValueError('Incomplete/faulty return route')
    if any(sha(Path(p))!=d for p,d in sources.items()):
        raise ValueError('Changed route source')
    sources[str(out/'capture.json')]=sha(out/'capture.json')
    (out/'school-return-report.json').write_text(json.dumps(dict(sources=sources,complete=True,
        scope='Read-only state-guided ordinary input. Same policy, independent encounters; '
              'completion alone is not timing, rendering or acoustic acceptance.'),indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--system',choices=('nes','snes'),required=True)
    for name in ('core','candidate','out'):p.add_argument('--'+name,type=Path,required=True)
    capture(**vars(p.parse_args()))
