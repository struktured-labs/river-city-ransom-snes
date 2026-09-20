"""Correct the experimental scanner's scalar continuation to instruction boundary $83D7."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
from tools import consumer_word_scan as word
from tools.benchmark_report import sha

assemble_previous=word.assemble
SCALAR=0x83d7
SCALAR_BYTES=bytes.fromhex('bd001d2902f062')


def validate_entry(image):
    if image[SCALAR:SCALAR+len(SCALAR_BYTES)]!=SCALAR_BYTES:
        raise ValueError('Scalar continuation is not LDA flags,X / AND #2 / BEQ next')


def assemble():
    code=assemble_previous()
    old=bytes.fromhex('4cd983');new=bytes.fromhex('4cd783')
    if code.count(old)!=1 or new in code:raise ValueError('Changed experimental continuation')
    return code.replace(old,new)


@contextmanager
def installed():
    previous=word.assemble
    try:
        word.assemble=assemble
        yield
    finally:word.assemble=previous


def build(parent,out):
    validate_entry((parent/'native-cpu.sfc').read_bytes())
    with installed():word.build(parent,out)
    p=out/'manifest.json';meta=json.loads(p.read_text());trial=meta['experimental_consumer_linear_scan']
    trial['sources'][str(Path(__file__))]=sha(Path(__file__))
    trial['scalar_entry_fix']=dict(address=SCALAR,preimage=SCALAR_BYTES.hex(),previous_wrong_target=0x83d9)
    trial['scope']+=' Corrected scalar continuation83D7;3573 and suffix variants mistakenly jumped into the LDA operand. '
    trial['scope']+='Their apparent latency improvements are invalid optimization evidence. Actual cartridge/replay gates required.'
    p.write_text(json.dumps(meta,indent=2)+'\n')


def replay(**args):
    validate_entry((args['trial']/'native-cpu.sfc').read_bytes())
    meta=json.loads((args['trial']/'manifest.json').read_text())['experimental_consumer_linear_scan']
    if meta.get('scalar_entry_fix',{}).get('address')!=SCALAR:raise ValueError('Need corrected entry build')
    with installed():valid=word.replay(**args)
    p=args['out']/'report.json';report=json.loads(p.read_text())
    report['row_scan_trial']['scalar_entry_fix']=SCALAR
    report['scope']+=' Corrected scalar entry83D7, guarded against actual ROM opcode bytes.'
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
