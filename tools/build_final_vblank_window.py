"""Reject wrapped scanline0 in final palette/display admission; require240<=line<254."""
import argparse
import json
from pathlib import Path
import shutil
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

HELPER=bytes.fromhex('a51cc9f09006c9feb00238601860')


def patch(original):
    if original[0x86c8:0x86e6]!=bytes.fromhex('ad12421017ad3721ad3d21851cad3d212901d008a51cc9feb00238601860'):
        raise ValueError('Changed final gate')
    if original[0x77d0:0x77d0+len(HELPER)]!=b'\xff'*len(HELPER):
        raise ValueError('Occupied helper')
    image=bytearray(original)
    image[0x86dc:0x86e4]=bytes.fromhex('4cd077eaeaeaeaea')
    image[0x77d0:0x77d0+len(HELPER)]=HELPER
    checksum(image)
    changes=[i for i,(a,b) in enumerate(zip(original,image)) if a!=b]
    if any(not (0x86dc<=i<0x86e4 or 0x77d0<=i<0x77d0+len(HELPER) or 0xffdc<=i<0xffe0) for i in changes):
        raise ValueError('Unrelated mutation')
    return image,changes


def build(parent,out):
    rom=parent/'native-cpu.sfc'
    if out.exists() or sha(rom)!='8ed9aafe6af975023bfd7fd24a9ca0419a6b82db7916099dc6ef2c31f902cc29':
        raise ValueError('Exact3764 and fresh output required')
    image,changes=patch(rom.read_bytes())
    out.mkdir(parents=True)
    for p in parent.iterdir():
        if p.is_file():shutil.copy2(p,out/p.name)
    (out/'native-cpu.sfc').write_bytes(image)
    meta=json.loads((parent/'manifest.json').read_text())
    paths=[Path(__file__),Path('tools/build_inline_pitch_trial.py'),rom,parent/'manifest.json']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_final_vblank_window=dict(
        sources={str(p):sha(p) for p in paths},changed_offsets=changes,helper=HELPER.hex(),
        release_ready=False,scope=__doc__+' Retains hardware VBlank/high-beam checks and transition '
        'rollback. Does not bypass final admission, force a visible transfer, or alter queue order.'))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'])))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):parser.add_argument('--'+k,type=Path,required=True)
    build(**vars(parser.parse_args()))
