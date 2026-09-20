"""Unique-head, fixed-phase rightward player movement check; no lag alignment."""
import argparse
import json
from pathlib import Path
import shutil
try:
    from .benchmark_report import verify_capture, sha
except ImportError:
    from benchmark_report import verify_capture, sha


def head_observation(row):
    ram = bytes.fromhex(row['game_ram_hex'])
    if len(ram) != 2048 or ram[0x42] != 0 or any(ram[0xDC:0xDE]):
        raise ValueError('Need original room-zero stationary-camera RAM')
    found=[]
    # OAM allocation changes when another actor enters. Search only the
    # original OAM array for this exact pose, never a nearest-position match.
    for slot in range(0x200,0x2FC,4):
        a,b=ram[slot:slot+4],ram[slot+4:slot+8]
        if (a[0] in (115,116) and b[0]==a[0] and a[1:3]==bytes((1,64))
                and b[1:3]==bytes((0,64)) and b[3]-a[3]==8):
            found.append(dict(slot=slot,x=a[3],y=a[0]))
    if len(found)!=1:
        raise ValueError('Need exactly one matching Alex head signature')
    return found[0]


def head_x(row):
    return head_observation(row)['x']


def compare_positions(reference, candidate):
    if len(reference) != 32 or len(candidate) != 32 or reference[0] != candidate[0]:
        raise ValueError('Need equal-start 32-frame movement windows')
    if any(b<a for values in (reference,candidate) for a,b in zip(values,values[1:])):
        raise ValueError('Movement is not monotonic')
    arrivals = []
    for position in sorted(set(reference)):
        target = reference.index(position)
        actual = next((i for i,x in enumerate(candidate) if x >= position), None)
        arrivals.append(dict(position=position, nes_frame=target+1,
                             snes_frame=None if actual is None else actual+1,
                             delay=None if actual is None else actual-target))
    return dict(reference_positions=reference, candidate_positions=candidate,
                displacement=[reference[-1]-reference[0],candidate[-1]-candidate[0]],
                arrivals=arrivals,
                passed=reference[-1] == candidate[-1] and reference[-1]>reference[0]
                       and all(a['delay'] is not None and a['delay']<=0 for a in arrivals))


def build(reference,candidate,out):
    positions=[]
    observations=[]
    for system,path in zip(('nes','snes'),(reference,candidate)):
        receipt,rows=verify_capture(path)
        if receipt['system']!=system or receipt['scenario_name']!='movement-probe' or not receipt['capture_complete'] or any(r['fault'] for r in rows):
            raise ValueError('Need complete fault-free movement-probe captures')
        if system == 'nes' and receipt['rom_sha256'] != receipt['templates']['menu']['source_rom']:
            raise ValueError('Wrong original NES reference')
        if any(r['input_requested'] != r['input_delivered'] for r in rows):
            raise ValueError('Movement inputs were not delivered')
        selected=[r for r in rows if r['phase'] in ('move_right','right_stop')]
        observed=[dict(frame=r['frame'],**head_observation(r)) for r in selected]
        observations.append(observed)
        positions.append([r['x'] for r in observed])
    result=compare_positions(*positions)
    result.update(schema='rcr-rightward-movement-v2',release_ready=False,
                  head_observations=observations,
                  capture_sha256=[sha(p/'capture.json') for p in (reference,candidate)],
                  scope='Fixed 24-frame Right plus 8-frame settling; no time alignment, not combat/leftward movement or full-game speed')
    out.mkdir(parents=True,exist_ok=False)
    html=['<!doctype html><meta charset="utf-8"><title>Rightward movement audit</title>',
          '<h1>Short rightward movement</h1>',
          '<p>Unique exact player-head signature across original OAM, 24 Right frames plus 8 settling frames. Slots and coordinates retained. No time alignment or nearest-position search. Enemy states differ; leftward/combat and loading are not certified.</p>',
          f'<p>Displacements NES/SNES: {result["displacement"]}; no-slower gate: {result["passed"]}.</p>']
    for system,path in zip(('nes','snes'),(reference,candidate)):
        shutil.copyfile(path/'move_right.png',out/f'{system}.png')
        html.append(f'<figure><figcaption>{system}</figcaption><img style="width:512px;image-rendering:pixelated" src="{system}.png"></figure>')
    html.append('<p><a href="report.json">Every observed position and first-arrival delay</a></p>')
    (out/'index.html').write_text('\n'.join(html))
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    return result['passed']


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('reference','candidate','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    raise SystemExit(0 if build(a.reference,a.candidate,a.out) else 1)
