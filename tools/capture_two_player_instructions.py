"""Instruction-control captures under the recorded two-port combat policy."""
import argparse
import json
from pathlib import Path

from tools import combat_campaign as combat
from tools.benchmark_report import sha, verify_capture
from tools.capture_combat_instructions import capture as instructions
from tools.two_player_combat import installed_policy, two_ports, validate_ports


def capture(core,candidate,policy,out,control=None,first=None,last=None):
    paths = [Path(__file__),Path('tools/two_player_combat.py'),
        Path('tools/capture_combat_instructions.py'),core]
    hashes = {str(p):sha(p) for p in paths}
    records=[]
    with installed_policy(),two_ports(core,records):
        instructions(core,candidate,policy,out,control,first,last)
    with installed_policy(),combat.installed(policy):
        receipt,rows=verify_capture(out)
    delivery=validate_ports(records,rows,'snes')
    (out/'two-port-input.json').write_text(json.dumps(records,separators=(',',':'))+'\n')
    if control is not None:
        if records!=json.loads((control/'two-port-input.json').read_text()):
            raise ValueError('Instruction observer changed port requests/delivery')
        paths += [control/'two-player-instructions.json',control/'two-port-input.json']
    if hashes!={p:sha(Path(p)) for p in hashes}:
        raise ValueError('Capture sources changed')
    paths += [out/'capture.json',out/'instruction-control.json',out/'two-port-input.json']
    report=dict(policy=policy,delivery=delivery,observer_neutral=control is not None,
        sources={str(p):sha(p) for p in paths},scope=__doc__)
    (out/'two-player-instructions.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(delivery))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','candidate','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--policy',choices=combat.POLICIES,required=True)
    p.add_argument('--control',type=Path)
    for name in ('first','last'):p.add_argument('--'+name,type=int)
    capture(**vars(p.parse_args()))
