"""Restore CHR-upload admission after moving the544-byte OAM transfer earlier."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from tools import replay_transition_commit_rows as replay_tool
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

PARENT_SHA='e8a6b2f57702fe2057276aa506917b4aa264c5de0dc3acf1d4893b4749cc40b4'
SITE=0x86be
PREIMAGE=bytes.fromhex('a51cc9f3b00238601860')
compose_parent=replay_tool.patch


def patch(image):
    if hashlib.sha256(image).hexdigest()!=PARENT_SHA:raise ValueError('Need exact transition3502 parent')
    if image[SITE:SITE+len(PREIMAGE)]!=PREIMAGE:raise ValueError('Changed CHR admission guard')
    data=bytearray(image);data[SITE+3]=246;checksum(data)
    changes=[i for i,(a,b) in enumerate(zip(image,data)) if a!=b]
    if any(i!=SITE+3 and not 0xffdc<=i<0xffe0 for i in changes):raise ValueError('Unrelated change')
    return bytes(data),changes


def build(parent,out):
    if out.exists():raise ValueError('Fresh output required')
    meta=json.loads((parent/'manifest.json').read_text())
    if meta['rom_sha256']!=sha(parent/'native-cpu.sfc'):raise ValueError('Changed parent manifest')
    image,changes=patch((parent/'native-cpu.sfc').read_bytes())
    paths=[Path(__file__),Path('tools/build_inline_pitch_trial.py'),parent/'native-cpu.sfc',parent/'manifest.json']
    out.mkdir()
    for p in parent.iterdir():
        if p.is_file():shutil.copy2(p,out/p.name)
    (out/'native-cpu.sfc').write_bytes(image)
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_early_oam_chr_slack=dict(
        sources={str(p):sha(p) for p in paths},changed_offsets=changes,cutoff_before=243,cutoff_after=246,
        release_ready=False,scope=__doc__+' Earlier OAM consumes over3scanlines before the CHR guard. '
        'Parent3502 never admits visible CHR jobs under the old cutoff. '
        'New cutoff requires actual full-envelope DMA safety and starvation/VRAM checks. '
        'Row249 and palette254 deadlines unchanged; no new graphics or SPC data.'))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'])))


def composed(image):
    parent,_=compose_parent(image)
    return patch(parent)


def replay(**args):
    original=replay_tool.patch
    try:
        replay_tool.patch=composed
        valid=replay_tool.replay(**args)
    finally:replay_tool.patch=original
    p=args['out']/'report.json';r=json.loads(p.read_text())
    meta=json.loads((args['trial']/'manifest.json').read_text())['experimental_early_oam_chr_slack']
    if any(sha(Path(p))!=h for p,h in meta['sources'].items()):raise ValueError('Changed patch dependencies')
    r['sources'].update(meta['sources']);r['sources'][str(Path(__file__))]=sha(Path(__file__))
    r['row_scan_trial']['chr_cutoff']=246
    r['scope']=__doc__+' Exact composition from3408; initial CPU/fullWRAM/VRAM equality required. '
    r['scope']+='All cross-ROM primary differences retained. Actual CHR transfers, DMA safety, sprite and audio qualification remain separate.'
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
