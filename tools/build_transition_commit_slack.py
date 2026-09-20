"""Transition rollback plus one scanline for its now palette-only final admission."""
import argparse
import json
from pathlib import Path

from tools import build_transition_display_commit as parent_tool
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

base_patch=parent_tool.patch


def patch(image,helper):
    data,_=base_patch(image,helper)
    if data[0x86dc:0x86e6]!=bytes.fromhex('a51cc9feb00238601860'):
        raise ValueError('Changed final palette guard')
    data=bytearray(data);data[0x86df]=255;checksum(data)
    return bytes(data),[i for i,(a,b) in enumerate(zip(image,data)) if a!=b]


def build(parent,out):
    original=parent_tool.patch
    try:
        parent_tool.patch=patch
        parent_tool.build(parent,out)
    finally:parent_tool.patch=original
    p=out/'manifest.json';meta=json.loads(p.read_text())
    meta['experimental_transition_display_commit'].update(final_cutoff=255,scope=__doc__+
        ' The cutoff254 rollback variant stalls at settings: repeated readiness scanning never admits final display. '
        'No DMA guard bypass. Actual full-envelope DMA end times must qualify cutoff255; not deployed.')
    meta['experimental_transition_display_commit']['sources'][str(Path(__file__))]=sha(Path(__file__))
    p.write_text(json.dumps(meta,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):p.add_argument('--'+k,type=Path,required=True)
    build(**vars(p.parse_args()))
