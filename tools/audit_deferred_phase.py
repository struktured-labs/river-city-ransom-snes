"""Measure every complete retained-NMI phase wait in a neutral instruction window."""
import argparse
import csv
import json
from pathlib import Path

from tools.audit_park_instructions import parse
from tools.benchmark_report import sha,verify_capture


def waits(rows,entry,done):
    active=None
    samples=[]
    iterations=0
    for row in rows:
        if row['pc']==entry:
            if active is None:
                active=row
                iterations=0
            iterations+=1
        elif row['pc']==done:
            if active is None:
                raise ValueError('Phase completion missing entry')
            elapsed=row['clock']-active['clock']
            if elapsed<=0:raise ValueError('Nonpositive phase interval')
            samples.append(dict(start=active,end=row,iterations=iterations,clocks=elapsed))
            active=None
    if active is not None:raise ValueError('Truncated phase wait')
    if not samples:raise ValueError('No phase waits observed')
    return samples


def audit(capture,normal,trace,candidate,out):
    receipt,rows=verify_capture(capture)
    control,baseline=verify_capture(normal)
    if rows!=baseline or not receipt['capture_complete'] or any(receipt[k]!=control[k]
            for k in ('rom_sha256','audio_sha256','scenario_sha256','frames')):
        raise ValueError('Incomplete or changed observation')
    binding=receipt['instruction_trace']
    if binding['sha256']!=sha(trace) or sha(candidate/'native-cpu.sfc')!=receipt['rom_sha256']:
        raise ValueError('Unbound trace/cartridge')
    labels={r.split()[2].lstrip('.'):int(r.split()[1],16)
        for r in (candidate/'native_boot.lbl').read_text().splitlines()}
    with trace.open() as f:instructions=parse(csv.reader(f),binding['first'],binding['last'])
    samples=waits(instructions,labels['@deferred_late_vblank'],labels['@deferred_late_vblank_done'])
    paths=(Path(__file__),Path('tools/audit_park_instructions.py'),candidate/'native_boot.lbl',
        candidate/'manifest.json',candidate/'native-cpu.sfc',capture/'capture.json',normal/'capture.json',trace)
    report=dict(observer_neutral=True,samples=samples,sources={str(p):sha(p) for p in paths},
        scope='All complete exact linked phase-guard entry/exit intervals in the bound CPU window. '
              'Repeated polling entries belong to one interval. No selection of faster samples; '
              'full game timeline and PCM match normal core. Not a whole-game speed claim.')
    out.mkdir(parents=True,exist_ok=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(samples=len(samples),clocks=[s['clocks'] for s in samples],
        iterations=[s['iterations'] for s in samples])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('capture','normal','trace','candidate','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
