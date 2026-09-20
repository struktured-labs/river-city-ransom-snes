"""Trace a short instruction window, reusing a verified same-core combat control."""
import argparse
import json
from pathlib import Path

from tools import combat_campaign as combat
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha, verify_capture
from tools.capture_combat_instructions import capture
from tools.two_player_combat import installed_policy, two_ports, validate_ports


def run(core, candidate, normal, policy, first, last, out):
    proof = bound_report(normal/'two-player.json')
    if proof['observed'] or proof['system'] != 'snes' or proof['policy'] != policy:
        raise ValueError('Need same-policy unobserved two-player control')
    old = json.loads((normal/'two-port-input.json').read_text())
    with installed_policy(), combat.installed(policy):
        receipt, rows = verify_capture(normal)
    if (receipt['core_sha256'] != sha(core) or receipt['rom_sha256'] != sha(candidate/'native-cpu.sfc') or
            validate_ports(old, rows, 'snes') != proof['delivery']):
        raise ValueError('Different control core/ROM/input')
    records = []
    with installed_policy(), two_ports(core, records):
        capture(core, candidate, policy, out, normal, first, last)
    if records != old:
        raise ValueError('Instruction observer changed controller delivery')
    report = bound_report(out/'instruction-control.json')
    report['sources'].update(proof['sources'])
    for p in (Path(__file__), Path('tools/two_player_combat.py'), normal/'two-player.json',
              normal/'two-port-input.json'):
        report['sources'][str(p)] = sha(p)
    report.update(two_player=True, control_reused=True, delivery=proof['delivery'], scope=__doc__)
    (out/'two-player-trace.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(observer_neutral=True, control_reused=True, window=[first,last])))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('core','candidate','normal','out'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--policy',choices=combat.POLICIES,required=True)
    for k in ('first','last'):p.add_argument('--'+k,type=int,required=True)
    run(**vars(p.parse_args()))
