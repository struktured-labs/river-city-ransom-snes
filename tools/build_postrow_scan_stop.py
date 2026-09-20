"""Stop late empty-row search after actual publication; retain final254 gate."""
import argparse
import json
from pathlib import Path
import shutil
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum


def build(parent,out):
    rom=parent/'native-cpu.sfc'
    if out.exists() or sha(rom)!='8174cf80af132e8345fdad8118da7044941c19c43bb9065d6cb594c486baffaf':
        raise ValueError('Exact3760 and fresh output required')
    original=rom.read_bytes()
    # A is dead on entry to the scanner; X/Y remain next cursor/remaining budget.
    # SEP; JSR row_room; BCC finish; REP; JMP existing scanner; JMP finish.
    helper=bytes.fromhex('e22020e4879005c2204c80734c4f84')
    if original[0x844c:0x844f]!=bytes.fromhex('4c9e83') or original[0x77c0:0x77c0+len(helper)]!=b'\xff'*len(helper):
        raise ValueError('Changed continuation or occupied helper')
    image=bytearray(original)
    image[0x844c:0x844f]=bytes.fromhex('4cc077')
    image[0x77c0:0x77c0+len(helper)]=helper
    checksum(image)
    changes=[i for i,(a,b) in enumerate(zip(original,image)) if a!=b]
    if any(not (0x844c<=i<0x844f or 0x77c0<=i<0x77c0+len(helper) or 0xffdc<=i<0xffe0) for i in changes):
        raise ValueError('Unrelated change')
    out.mkdir(parents=True)
    for p in parent.iterdir():
        if p.is_file():shutil.copy2(p,out/p.name)
    (out/'native-cpu.sfc').write_bytes(image)
    meta=json.loads((parent/'manifest.json').read_text())
    paths=[Path(__file__),Path('tools/build_inline_pitch_trial.py'),rom,parent/'manifest.json']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_postrow_scan_stop=dict(
        sources={str(p):sha(p) for p in paths},changed_offsets=changes,helper=helper.hex(),
        release_ready=False,scope=__doc__+' Uses same252 row check, including forced-blank bypass. '
        'No skipped-ready flags are retired; saved cursor points to the next unexamined row.'))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'])))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):parser.add_argument('--'+k,type=Path,required=True)
    build(**vars(parser.parse_args()))
