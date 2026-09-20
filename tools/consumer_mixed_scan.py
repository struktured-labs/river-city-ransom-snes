"""Keep fast empty-group reduction while avoiding repeated searches in mixed groups."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import subprocess
import tempfile
from tools import consumer_linear_scan as base
from tools.consumer_word_entry_fix import validate_entry
from tools.benchmark_report import sha


def assemble():
    with tempfile.TemporaryDirectory(prefix='rcr-consumer-mixed-') as temp:
        obj=Path(temp)/'helper.o';binary=Path(temp)/'helper.bin'
        subprocess.run(['.deps/cc65/bin/ca65','-o',str(obj),'snes/consumer_mixed_scan.asm'],check=True)
        subprocess.run(['.deps/cc65/bin/ld65','-C','snes/consumer_linear_scan.cfg','-o',str(binary),str(obj)],check=True)
        return binary.read_bytes()


@contextmanager
def installed():
    previous=base.assemble
    try:
        base.assemble=assemble
        yield
    finally:base.assemble=previous


def build(parent,out):
    validate_entry((parent/'native-cpu.sfc').read_bytes())
    with installed():base.build(parent,out)
    p=out/'manifest.json';meta=json.loads(p.read_text());trial=meta['experimental_consumer_linear_scan']
    trial['sources'].update({str(p):sha(p) for p in (Path(__file__),Path('snes/consumer_mixed_scan.asm'),
        Path('tools/consumer_word_entry_fix.py'))})
    trial['mixed_scan']=True
    trial['scope']=__doc__+' Bounded indexed flag reads, exact queue order and scan budget. Verified83D7 scalar '
    trial['scope']+='continuation. No new state, DP scratch, producer, OAM, deadlines or audio changes. Not release-ready.'
    p.write_text(json.dumps(meta,indent=2)+'\n')


def replay(**args):
    validate_entry((args['trial']/'native-cpu.sfc').read_bytes())
    meta=json.loads((args['trial']/'manifest.json').read_text())['experimental_consumer_linear_scan']
    if not meta.get('mixed_scan'):raise ValueError('Need mixed-scan candidate')
    with installed():valid=base.replay(**args)
    p=args['out']/'report.json';report=json.loads(p.read_text())
    report['row_scan_trial']['mixed_scan']=True
    report['scope']=__doc__+' Exact guarded3408 composition, same initial fullCPU/WRAM/VRAM and all differences retained. '
    report['scope']+='Correct83D7 continuation. Prior experiments retained. Not broad qualification.'
    p.write_text(json.dumps(report,indent=2)+'\n')
    return valid


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='mode',required=True)
    b=s.add_parser('build');r=s.add_parser('replay')
    for k in ('parent','out'):b.add_argument('--'+k,type=Path,required=True)
    for k in ('core','candidate','normal','checkpoint-report','out','trial','resume-control'):
        r.add_argument('--'+k,type=Path,required=True)
    for k in ('frame','frames'):r.add_argument('--'+k,type=int,required=True)
    args=vars(p.parse_args());mode=args.pop('mode')
    if mode=='build':build(**args)
    else:raise SystemExit(0 if replay(**args) else 1)
