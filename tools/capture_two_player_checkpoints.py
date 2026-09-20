"""Exact normal-control checkpoint capture for either two-player combat policy."""
import argparse
import json
from pathlib import Path

from tools import capture_combat_checkpoints as checkpoint
from tools.benchmark_report import sha
from tools.two_player_combat import installed_policy,two_ports
from tools.combat_campaign import POLICIES


def capture(core,candidate,normal,frames,out,policy):
    records=[]
    with installed_policy(),two_ports(core,records):
        passed=checkpoint.capture(core,candidate,normal,frames,out,policy)
    if records!=json.loads((normal/'two-port-input.json').read_text()):
        raise ValueError('Checkpoint observation changed controller requests/delivery')
    inputs=out/'two-port-input.json'
    inputs.write_text(json.dumps(records,separators=(',',':'))+'\n')
    report=json.loads((out/'checkpoint-report.json').read_text())
    for p in (Path(__file__),Path('tools/two_player_combat.py'),inputs,normal/'two-port-input.json'):
        report['sources'][str(p)]=sha(p)
    report['two_player']=True
    (out/'checkpoint-report.json').write_text(json.dumps(report,indent=2)+'\n')
    return passed


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('core','candidate','normal','out'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--frames',required=True)
    p.add_argument('--policy',choices=POLICIES,required=True)
    raise SystemExit(0 if capture(**vars(p.parse_args())) else 1)
