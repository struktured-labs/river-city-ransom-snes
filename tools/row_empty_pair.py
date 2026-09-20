"""Coalesce two empty row-scan groups without changing queue order or DMA deadlines."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from tools import replay_transition_commit_rows as replay_tool
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

PARENT_SHA='e8a6b2f57702fe2057276aa506917b4aa264c5de0dc3acf1d4893b4749cc40b4'
SITE=0x83bd
HELPER=0x7380
compose_parent=replay_tool.patch


def assemble():
    with tempfile.TemporaryDirectory(prefix='rcr-empty-pair-') as temp:
        obj=Path(temp)/'helper.o';binary=Path(temp)/'helper.bin'
        subprocess.run(['.deps/cc65/bin/ca65','-o',str(obj),'snes/row_empty_pair.asm'],check=True)
        subprocess.run(['.deps/cc65/bin/ld65','-C','snes/row_empty_pair.cfg','-o',str(binary),str(obj)],check=True)
        return binary.read_bytes()


def patch(image,helper):
    if hashlib.sha256(image).hexdigest()!=PARENT_SHA:raise ValueError('Need exact transition3502 parent')
    if image[SITE:SITE+5]!=bytes.fromhex('8a18690800') or image[HELPER:HELPER+256]!=b'\xff'*256 or not 0<len(helper)<=256:
        raise ValueError('Changed empty-skip entry or occupied helper')
    data=bytearray(image);data[SITE:SITE+5]=bytes.fromhex('4c8073eaea');data[HELPER:HELPER+len(helper)]=helper
    checksum(data)
    changes=[i for i,(a,b) in enumerate(zip(image,data)) if a!=b]
    if any(not(SITE<=i<SITE+5 or HELPER<=i<HELPER+len(helper) or 0xffdc<=i<0xffe0) for i in changes):
        raise ValueError('Unrelated ROM change')
    return bytes(data),changes


def build(parent,out):
    if out.exists():raise ValueError('Fresh output required')
    meta=json.loads((parent/'manifest.json').read_text())
    if sha(parent/'native-cpu.sfc')!=meta['rom_sha256']:raise ValueError('Changed parent manifest')
    helper=assemble();image,changes=patch((parent/'native-cpu.sfc').read_bytes(),helper)
    paths=[Path(__file__),Path('snes/row_empty_pair.asm'),Path('snes/row_empty_pair.cfg'),
           Path('tools/build_inline_pitch_trial.py'),Path('.deps/cc65/bin/ca65'),Path('.deps/cc65/bin/ld65'),
           parent/'native-cpu.sfc',parent/'manifest.json']
    out.mkdir()
    for p in parent.iterdir():
        if p.is_file():shutil.copy2(p,out/p.name)
    (out/'native-cpu.sfc').write_bytes(image);(out/'row-empty-pair.bin').write_bytes(helper)
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_row_empty_pair=dict(
        sources={str(p):sha(p) for p in paths},changed_offsets=changes,helper_hex=helper.hex(),
        release_ready=False,scope=__doc__+' Both eight-row groups must lack staged-ready bits; flags1 may be skipped, '
        'flags2/3 never skipped. Exact bounded ring visitation retained; no DMA/producer/audio changes.'))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'],helper_bytes=len(helper))))


def composed(image):
    parent,_=compose_parent(image)
    return patch(parent,assemble())


def replay(**args):
    original=replay_tool.patch
    try:
        replay_tool.patch=composed
        valid=replay_tool.replay(**args)
    finally:replay_tool.patch=original
    p=args['out']/'report.json';r=json.loads(p.read_text())
    m=json.loads((args['trial']/'manifest.json').read_text())['experimental_row_empty_pair']
    if any(sha(Path(p))!=h for p,h in m['sources'].items()):raise ValueError('Changed empty-scan dependencies')
    r['sources'].update(m['sources']);r['sources'][str(Path(__file__))]=sha(Path(__file__))
    r['row_scan_trial']['empty_pair_scan']=True
    r['scope']=__doc__+' Exact composition from authenticated3408 state; unchanged initial CPU/fullWRAM/VRAM. '
    r['scope']+='All cross-ROM primary differences retained. Restored test does not replace boot, DMA, sprite or audio qualification.'
    p.write_text(json.dumps(r,indent=2)+'\n')
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
