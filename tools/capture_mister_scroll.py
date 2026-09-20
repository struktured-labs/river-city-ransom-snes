"""Record a bounded horizontal-traversal episode with the proven dual recorder."""
import argparse
from pathlib import Path

from tools import capture_mister_dual_audio as capture


def episode():
    def step(keys, seconds):return dict(keys=keys,seconds=seconds)
    # Begin paused on a verified street. Release every jump while holding
    # direction. This requests traversal, it does not assert camera movement.
    events=[step([],1),step(['start'],.15),step([], .2)]
    for _ in range(32):
        events.extend([step(['right','a'],.3),step(['right'],.2)])
    for _ in range(8):
        events.extend([step(['left','a'],.3),step(['left'],.2)])
    return events+[step([], .2),step(['start'],.15),step([],1)]


def run(out,remote_out):
    # Only replace this process's explicit input policy. Recorder, ready
    # handshake, pad validation, bounded duration and cleanup stay unchanged.
    from tools.benchmark_report import sha
    import json
    original=capture.episode
    capture.episode=episode
    try:capture.capture(out,remote_out,raw_debug=True)
    finally:
        capture.episode=original
        report=out/'report.json'
        if report.exists():
            r=json.loads(report.read_text());r['sources'][str(Path(__file__))]=sha(Path(__file__))
            r['input_policy']='paused-street-horizontal-traversal';r['physical_scroll_verified']=False
            report.write_text(json.dumps(r,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('out','remote-out'):p.add_argument('--'+name,type=Path,required=True)
    run(**vars(p.parse_args()))
