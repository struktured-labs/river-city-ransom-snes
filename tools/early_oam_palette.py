"""Early OAM with explicit palette DMA mode/bank, formerly initialized by late OAM."""
import argparse
import json
from pathlib import Path

from tools import early_oam_scan as prototype
from tools import replay_row_scan_checkpoint as replay_tool
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

prototype_patch = prototype.patch


def patch(image):
    data, _ = prototype_patch(image)
    data=bytearray(data)
    # VRAM/CHR work can replace both DMA mode and source bank after early OAM.
    # Restore the palette's former precondition explicitly, then skip old OAM.
    data[0x8464:0x846f]=bytes.fromhex('9c0043a97e8d04434c8884')
    checksum(data)
    return bytes(data),[i for i,(a,b) in enumerate(zip(image,data)) if a!=b]


def build(parent,out):
    original=prototype.patch
    try:
        prototype.patch=patch
        prototype.build(parent,out)
    finally:prototype.patch=original
    p=out/'manifest.json';r=json.loads(p.read_text())
    r['experimental_full_row_scan']['sources'][str(Path(__file__))]=sha(Path(__file__))
    r['experimental_full_row_scan'].update(explicit_palette_mode_bank=True,scope=__doc__)
    p.write_text(json.dumps(r,indent=2)+'\n')


def replay(**args):
    original=replay_tool.patch
    try:
        replay_tool.patch=patch
        passed=replay_tool.replay(**args)
    finally:replay_tool.patch=original
    p=args['out']/'report.json';r=json.loads(p.read_text())
    r['row_scan_trial'].update(early_oam=True,explicit_palette_mode_bank=True,row_cutoff=249)
    r['sources'].update({str(p):sha(p) for p in (Path(__file__),Path('tools/early_oam_scan.py'))})
    r['scope']=(__doc__+' Same-ROM uninterrupted control and identical initial CPU/WRAM/VRAM required. '
        'All later differences retained. No restored observer clocks used. DMA and sprite qualification remain separate.')
    p.write_text(json.dumps(r,indent=2)+'\n')
    return passed


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);subs=p.add_subparsers(dest='mode',required=True)
    b=subs.add_parser('build');r=subs.add_parser('replay')
    for k in ('parent','out'):b.add_argument('--'+k,type=Path,required=True)
    for k in ('core','candidate','normal','checkpoint-report','out','trial','resume-control'):
        r.add_argument('--'+k,type=Path,required=True)
    for k in ('frame','frames'):r.add_argument('--'+k,type=int,required=True)
    args=vars(p.parse_args());mode=args.pop('mode')
    if mode=='build':build(**args)
    else:raise SystemExit(0 if replay(**args) else 1)
