"""Test one or two more row-admission scanlines after sprites already transferred."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from tools import early_oam_chr_slack as replay_tool
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

PARENT_SHA='635f21cd2f7951dd3e8acf07fabfb8acdc68302518f1bdb942a3a3fd8d4c71e3'
SITE=0x87fd
compose_parent=replay_tool.composed


def patch(image,cutoff):
    if cutoff not in (250,251):raise ValueError('Only one/two additional row scanlines under test')
    if hashlib.sha256(image).hexdigest()!=PARENT_SHA:raise ValueError('Need exact CHR-restored3527 parent')
    if image[SITE:SITE+10]!=bytes.fromhex('a51cc9f9b00238601860'):raise ValueError('Changed row-room guard')
    data=bytearray(image);data[SITE+3]=cutoff;checksum(data)
    changes=[i for i,(a,b) in enumerate(zip(image,data)) if a!=b]
    if any(i!=SITE+3 and not 0xffdc<=i<0xffe0 for i in changes):raise ValueError('Unrelated change')
    return bytes(data),changes


def build(parent,out,cutoff):
    if out.exists():raise ValueError('Fresh output required')
    meta=json.loads((parent/'manifest.json').read_text())
    if sha(parent/'native-cpu.sfc')!=meta['rom_sha256']:raise ValueError('Changed parent manifest')
    image,changes=patch((parent/'native-cpu.sfc').read_bytes(),cutoff)
    paths=[Path(__file__),Path('tools/build_inline_pitch_trial.py'),parent/'native-cpu.sfc',parent/'manifest.json']
    out.mkdir()
    for p in parent.iterdir():
        if p.is_file():shutil.copy2(p,out/p.name)
    (out/'native-cpu.sfc').write_bytes(image)
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_early_oam_row_slack=dict(
        sources={str(p):sha(p) for p in paths},changed_offsets=changes,cutoff_before=249,cutoff_after=cutoff,
        release_ready=False,scope=__doc__+' No sprite, CHR246, palette254, byte budget or queue-order changes. '
        'Visible row transfer remains at most128 bytes per batch. Actual DMA safety and final palette publication '
        'must be qualified independently; no blanket timing waiver.'))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'],row_cutoff=cutoff)))


def replay(**args):
    meta=json.loads((args['trial']/'manifest.json').read_text())['experimental_early_oam_row_slack']
    if any(sha(Path(p))!=h for p,h in meta['sources'].items()):raise ValueError('Changed row-slack dependency')
    def composed(image):
        parent,_=compose_parent(image)
        return patch(parent,meta['cutoff_after'])
    original=replay_tool.composed
    try:
        replay_tool.composed=composed
        valid=replay_tool.replay(**args)
    finally:replay_tool.composed=original
    p=args['out']/'report.json';r=json.loads(p.read_text())
    r['sources'].update(meta['sources']);r['sources'][str(Path(__file__))]=sha(Path(__file__))
    r['row_scan_trial']['row_cutoff']=meta['cutoff_after']
    r['scope']=__doc__+' Exact guarded composition from3408; same initial CPU/fullWRAM/VRAM required. '
    r['scope']+='All primary differences retained. No restored historical observers; not a DMA/palette/speed/audio release verdict.'
    p.write_text(json.dumps(r,indent=2)+'\n')
    return valid


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='mode',required=True)
    b=s.add_parser('build');r=s.add_parser('replay')
    for k in ('parent','out'):b.add_argument('--'+k,type=Path,required=True)
    b.add_argument('--cutoff',type=int,required=True)
    for k in ('core','candidate','normal','checkpoint-report','out','trial','resume-control'):
        r.add_argument('--'+k,type=Path,required=True)
    for k in ('frame','frames'):r.add_argument('--'+k,type=int,required=True)
    args=vars(p.parse_args());mode=args.pop('mode')
    if mode=='build':build(**args)
    else:raise SystemExit(0 if replay(**args) else 1)
