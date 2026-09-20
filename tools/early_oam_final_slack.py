"""Return three already-spent OAM scanlines to the now palette-only final batch."""
import argparse
import json
from pathlib import Path

from tools import early_oam_palette as prior
from tools import replay_row_scan_checkpoint as replay_tool
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

prior_patch = prior.patch


def patch(image):
    data, _ = prior_patch(image)
    if data[0x86dc:0x86e6] != bytes.fromhex('a51cc9fbb00238601860'):
        raise ValueError('Changed palette-only final guard')
    result = bytearray(data); result[0x86df] = 254; checksum(result)
    return bytes(result), [i for i,(a,b) in enumerate(zip(image,result)) if a!=b]


def build(parent,out):
    original=prior.patch
    try:
        prior.patch=patch
        prior.build(parent,out)
    finally:prior.patch=original
    p=out/'manifest.json';r=json.loads(p.read_text())
    r['experimental_full_row_scan']['sources'][str(Path(__file__))]=sha(Path(__file__))
    r['experimental_full_row_scan'].update(final_palette_cutoff=254,scope=__doc__+
        ' OAM already transfers early; final batch now contains64 palette bytes and registers only. '
        'Earlier sprite-first candidate starves this batch and remains forced blank at boot. '
        'Actual full-envelope DMA qualification is mandatory; not a waiver of VBlank safety.')
    p.write_text(json.dumps(r,indent=2)+'\n')


def replay(**args):
    original=replay_tool.patch
    try:
        replay_tool.patch=patch
        passed=replay_tool.replay(**args)
    finally:replay_tool.patch=original
    p=args['out']/'report.json';r=json.loads(p.read_text())
    r['row_scan_trial'].update(early_oam=True,explicit_palette_mode_bank=True,row_cutoff=249,final_palette_cutoff=254)
    r['sources'].update({str(p):sha(p) for p in (Path(__file__),Path('tools/early_oam_palette.py'),Path('tools/early_oam_scan.py'))})
    r['scope']=(__doc__+' Exact pinned composition; same-ROM uninterrupted control and identical initial CPU/WRAM/VRAM required. '
        'All later differences retained. No restored observer clocks; replay does not establish DMA safety.')
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
