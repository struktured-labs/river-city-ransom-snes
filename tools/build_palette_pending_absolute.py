"""Correct the palette flag probe to absolute003E; native direct page is1E00."""
import argparse
import json
from pathlib import Path
from tools import build_palette_pending_row_room as prior
from tools.benchmark_report import sha

previous_assemble=prior.assemble


def assemble():
    code=previous_assemble()
    if code[:2]!=bytes.fromhex('a53e') or len(code)!=24:
        raise ValueError('Changed retained faulty direct-page variant')
    # Only relative branches/RTS follow this load, so no absolute relocation.
    return bytes.fromhex('ad3e00')+code[2:]


def build(parent,out):
    old=prior.assemble
    try:
        prior.assemble=assemble
        prior.build(parent,out)
    finally:prior.assemble=old
    path=out/'manifest.json';meta=json.loads(path.read_text())
    trial=meta['experimental_palette_pending_row_room']
    trial['sources'][str(Path(__file__))]=sha(Path(__file__))
    trial['scope']+=' '+__doc__+' Faulty3798 is retained and rejected by the addressing test.'
    trial['absolute_flag_load']=True
    path.write_text(json.dumps(meta,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):parser.add_argument('--'+k,type=Path,required=True)
    build(**vars(parser.parse_args()))
