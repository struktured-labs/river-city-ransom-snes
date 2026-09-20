"""Test row cutoff252 only after suffix search savings; final254 remains mandatory."""
import argparse
import json
from pathlib import Path
import shutil
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum


def build(parent,out):
    rom=parent/'native-cpu.sfc'
    if out.exists() or sha(rom)!='f5cc5acc3a455c26e950d442d609538f16fa512b1cc9c525389df7b626e3faf4':
        raise ValueError('Exact3755 and fresh output required')
    original=rom.read_bytes()
    if original[0x87fd:0x8807]!=bytes.fromhex('a51cc9f9b00238601860'):
        raise ValueError('Changed row guard')
    image=bytearray(original); image[0x8800]=252; checksum(image)
    changes=[i for i,(a,b) in enumerate(zip(original,image)) if a!=b]
    if any(i!=0x8800 and not 0xffdc<=i<0xffe0 for i in changes):
        raise ValueError('Unrelated change')
    out.mkdir(parents=True)
    for p in parent.iterdir():
        if p.is_file():shutil.copy2(p,out/p.name)
    (out/'native-cpu.sfc').write_bytes(image)
    meta=json.loads((parent/'manifest.json').read_text())
    paths=[Path(__file__),Path('tools/build_inline_pitch_trial.py'),rom,parent/'manifest.json']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_suffix_row_budget=dict(
        sources={str(p):sha(p) for p in paths},changed_offsets=changes,
        row_cutoff=252,final_cutoff=254,release_ready=False,
        scope=__doc__+' Requires independent final-publication liveness and DMA qualification.'))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'])))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):parser.add_argument('--'+k,type=Path,required=True)
    build(**vars(parser.parse_args()))
