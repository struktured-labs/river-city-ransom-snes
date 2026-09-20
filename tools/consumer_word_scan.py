"""Scan each consumer flag word once, including mixed-ready groups and odd cursors."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import subprocess
import tempfile
from tools import consumer_linear_scan as base
from tools.benchmark_report import sha


def assemble():
    with tempfile.TemporaryDirectory(prefix='rcr-consumer-word-') as temp:
        obj=Path(temp)/'helper.o';binary=Path(temp)/'helper.bin'
        subprocess.run(['.deps/cc65/bin/ca65','-o',str(obj),'snes/consumer_word_scan.asm'],check=True)
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
    with installed():base.build(parent,out)
    p=out/'manifest.json';meta=json.loads(p.read_text());trial=meta['experimental_consumer_linear_scan']
    trial['sources'].update({str(p):sha(p) for p in (Path(__file__),Path('snes/consumer_word_scan.asm'))})
    trial['word_scan']=True
    trial['scope']=__doc__+' Replaces suffix unrolling with four bounded indexed BIT tests; locates the first '
    trial['scope']+='ready byte without repeated group scans. No new state or DP scratch. Exact ring order and '
    trial['scope']+='visit budget; unchanged producer, OAM, CHR/row/palette deadlines and audio. Not release-ready.'
    p.write_text(json.dumps(meta,indent=2)+'\n')


def replay(**args):
    meta=json.loads((args['trial']/'manifest.json').read_text())['experimental_consumer_linear_scan']
    if not meta.get('word_scan'):raise ValueError('Need word-scan candidate')
    with installed():valid=base.replay(**args)
    p=args['out']/'report.json';report=json.loads(p.read_text())
    report['row_scan_trial']['word_scan']=True
    report['scope']=__doc__+' Exact guarded3408 composition, same initial fullCPU/WRAM/VRAM and all differences retained. '
    report['scope']+='No suffix unrolling; prior3559/3569 boot failures retained. Not broad qualification.'
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
