"""Atomic transition display with a faster, equivalent readiness scan; cutoff stays254."""
import argparse
import json
from pathlib import Path

from tools import build_transition_display_commit as parent_tool
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

base_patch=parent_tool.patch
START=0x86f8
END=0x87e4
ABS_SCAN=bytes.fromhex('ad801e')+b''.join(bytes((0x0d,offset,0x1e)) for offset in range(0x82,0x100,2))
DIRECT_SCAN=bytes.fromhex('a580')+b''.join(bytes((0x05,offset)) for offset in range(0x82,0x100,2))
TAIL=b''.join(bytes((0x0d,offset,0x1d)) for offset in range(0x80,0x98,2))+bytes.fromhex('e220d0039ca01c60')


def patch(image,helper):
    data,_=base_patch(image,helper)
    if data[START:END]!=ABS_SCAN+TAIL:
        raise ValueError('Changed readiness scan or trailing branches')
    data=bytearray(data)
    replacement=DIRECT_SCAN+TAIL
    data[START:END]=replacement+b'\xea'*(END-START-len(replacement))
    checksum(data)
    return bytes(data),[i for i,(a,b) in enumerate(zip(image,data)) if a!=b]


def build(parent,out):
    original=parent_tool.patch
    try:
        parent_tool.patch=patch
        parent_tool.build(parent,out)
    finally:parent_tool.patch=original
    p=out/'manifest.json';meta=json.loads(p.read_text())
    meta['experimental_transition_display_commit'].update(final_cutoff=254,readiness_direct_page=True,
        readiness_saved_cpu_cycles=64,scope=__doc__+
        ' Native publisher DP is already1E00. The same64 transition words and12 CHR words are checked. '
        'No cached readiness, omitted flags, expanded VBlank deadline or added WRAM state. '
        'Cutoff255 variant is retained as rejected after VBlank overrun. Not deployed.')
    meta['experimental_transition_display_commit']['sources'][str(Path(__file__))]=sha(Path(__file__))
    p.write_text(json.dumps(meta,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):p.add_argument('--'+k,type=Path,required=True)
    build(**vars(p.parse_args()))
