"""Run authenticated health/dialogue probes for the isolated empty-tail candidate."""
import argparse
import json
from pathlib import Path
from tools import consumer_linear_scan as base
from tools.consumer_empty_tail import assemble
from tools.benchmark_report import sha


def replay(**args):
    meta=json.loads((args['trial']/'manifest.json').read_text())['experimental_consumer_empty_tail']
    for p,h in meta['sources'].items():
        if sha(Path(p))!=h:raise ValueError('Changed empty-tail dependency')
    original=base.assemble
    try:
        base.assemble=assemble
        valid=base.replay(**args)
    finally:base.assemble=original
    p=args['out']/'report.json';r=json.loads(p.read_text())
    r['sources'].update(meta['sources'])
    r['sources'][str(Path(__file__))]=sha(Path(__file__))
    r['row_scan_trial']['empty_tail']=True
    r['scope']=__doc__+' Exact composed cartridge, same initial full CPU/WRAM/VRAM, '
    r['scope']+='unchanged input and every primary difference retained. No physical acceptance implied.'
    p.write_text(json.dumps(r,indent=2)+'\n')
    return valid


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('core','candidate','normal','checkpoint-report','out','trial','resume-control'):
        p.add_argument('--'+k,type=Path,required=True)
    for k in ('frame','frames'):p.add_argument('--'+k,type=int,required=True)
    raise SystemExit(0 if replay(**vars(p.parse_args())) else 1)
