"""Check arrival delays around the fast-poll boundary, including starvation risk."""
import argparse
import json
from pathlib import Path
import time
from tools.check_timed_receiver import case
from tools.review_command_priority import bound
from tools.benchmark_report import sha


def check(fixture,out):
    if out.exists():raise ValueError('Fresh output required')
    start=time.monotonic();m=bound(fixture/'manifest.json')
    proof=Path('.deps/snes9x-timed-receiver-4061/timed-core.json');c=bound(proof);core=Path(c['core'])
    b=(fixture/'engine.bin').read_bytes()
    if sha(fixture/'engine.bin')!=m['engine_sha256']:raise ValueError('Changed engine')
    cases=[case(core,b,m['layout'],m['labels'],mode,delay,deadline,127)
        for mode in (0,128) for deadline in (0,32) for delay in range(0,513,16)]
    paths=[Path(__file__),Path('tools/check_timed_receiver.py'),Path('tools/check_sweep_driver.py'),
        fixture/'manifest.json',fixture/'engine.bin',proof,core]
    report=dict(passed=all(r['passed'] for r in cases),cases=cases,seconds=time.monotonic()-start,
        sources={str(p):sha(p) for p in paths},scope=__doc__,release_ready=False)
    out.mkdir();(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'],seconds=report['seconds'],cases=len(cases),
        failures=[{k:r[k] for k in ('mode','delay','deadline','errors')} for r in cases if not r['passed']])))
    if not report['passed']:raise ValueError('Arrival sweep failed')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('fixture','out'):p.add_argument('--'+k,type=Path,required=True)
    check(**vars(p.parse_args()))
