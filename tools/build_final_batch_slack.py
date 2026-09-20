"""Experimental one-line final-batch slack; requires measured VBlank safety qualification."""
import argparse
import json
from pathlib import Path

from tools.build_owned_queue_priority import build as priority
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_retained_producer_guard import symbols


def build(parent,out):
    priority(parent,out)
    meta=json.loads((out/'manifest.json').read_text());b=symbols(out/'native_boot.lbl')
    image=bytearray((out/'native-cpu.sfc').read_bytes());start=b['final_room']
    needle=bytes.fromhex('a51cc9fab00238601860');chunk=image[start:start+40]
    if chunk.count(needle)!=1:raise ValueError('Changed final-room guard')
    at=start+chunk.index(needle)+3;image[at]=251;checksum(image)
    (out/'native-cpu.sfc').write_bytes(image)
    files=[Path(__file__),out/'native_boot.lbl',parent/'manifest.json',parent/'native-cpu.sfc']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_final_batch_slack=dict(
        site=at,before=250,after=251,sources={str(p):sha(p) for p in files},
        release_ready=False,scope=__doc__))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'],final_batch_cutoff=251)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):p.add_argument('--'+k,type=Path,required=True)
    build(**vars(p.parse_args()))
