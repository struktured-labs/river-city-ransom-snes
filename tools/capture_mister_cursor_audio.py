"""Eight menu-navigation sound cues while gameplay remains paused throughout."""
import argparse
import json
from pathlib import Path

from tools import capture_mister_dual_audio as controller
from tools.benchmark_report import sha


def episode():
    events=[dict(keys=[],seconds=2)]
    for direction in ('right','left'):
        for _ in range(4):
            events.extend([dict(keys=[direction],seconds=.15),dict(keys=[],seconds=1.35)])
    return events+[dict(keys=[],seconds=5)]


def capture(out,remote_out):
    digest=sha(Path(__file__));original=controller.episode
    controller.episode=episode
    try:controller.capture(out,remote_out,raw_debug=True)
    finally:controller.episode=original
    if sha(Path(__file__))!=digest:raise ValueError('Cursor input policy changed during capture')
    path=out/'report.json';receipt=json.loads(path.read_text())
    receipt['sources'][str(Path(__file__))]=digest
    receipt['episode_name']='pause-selector-eight-cues'
    receipt['declared_events']=episode()
    receipt['scope']='Four Right taps and four Left taps; no Start, confirm, movement in gameplay, '
    receipt['scope']+='ROM writes or restart. Requires independently verified paused selector at start/end.'
    path.write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--remote-out',type=Path,required=True)
    capture(**vars(parser.parse_args()))
