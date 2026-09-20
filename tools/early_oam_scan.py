"""Publish prepared sprites before background searches, retaining bounded row DMA."""
import argparse
import json
from pathlib import Path
import shutil

from tools import replay_row_scan_checkpoint as replay_tool
from tools.benchmark_report import sha
from tools.build_full_row_scan import patch as full_patch
from tools.build_inline_pitch_trial import checksum

OAM = bytes.fromhex('9c02219c03219c0043a9048d0143a200508e0243a97e8d0443a220028e0543a9018d0b42')
HELPER = 0x7300


def patch(image):
    full, _ = full_patch(image)
    if (full[0x8464:0x8488] != OAM or full[0x82b6:0x82bb] != bytes.fromhex('a9808d1521')
            or full[HELPER:HELPER+256] != b'\xff'*256
            or full[0x87fd:0x8801] != bytes.fromhex('a51cc9f6')):
        raise ValueError('Changed OAM/entry/row deadline or occupied helper')
    data = bytearray(full)
    helper = OAM+bytes.fromhex('a9808d152160')
    data[HELPER:HELPER+len(helper)] = helper
    data[0x82b6:0x82bb] = bytes.fromhex('200073eaea')
    data[0x8464:0x8467] = bytes.fromhex('4c8884')
    # 544-byte OAM transfer has already consumed >3 scanlines. Give rows
    # only three back; final palette/register deadline stays unchanged.
    data[0x8800] = 249
    checksum(data)
    changes = [i for i,(a,b) in enumerate(zip(image,data)) if a != b]
    allowed = {0x838e,0x8800} | set(range(HELPER,HELPER+len(helper))) | set(range(0x82b6,0x82bb)) | set(range(0x8464,0x8467)) | set(range(0xffdc,0xffe0))
    if any(i not in allowed for i in changes): raise ValueError('Unrelated ROM mutation')
    return bytes(data), changes


def build(parent, out):
    if out.exists(): raise ValueError('Fresh candidate required')
    image, changes = patch((parent/'native-cpu.sfc').read_bytes())
    meta = json.loads((parent/'manifest.json').read_text())
    if sha(parent/'native-cpu.sfc') != meta['rom_sha256']: raise ValueError('Changed parent')
    out.mkdir()
    for p in parent.iterdir():
        if p.is_file(): shutil.copy2(p,out/p.name)
    (out/'native-cpu.sfc').write_bytes(image)
    paths=[Path(__file__),Path('tools/build_full_row_scan.py'),Path('tools/build_inline_pitch_trial.py'),
           parent/'manifest.json',parent/'native-cpu.sfc']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_full_row_scan=dict(
        sources={str(p):sha(p) for p in paths},changes=changes,early_oam=True,row_cutoff=249,
        release_ready=False,scope=__doc__+' Exact original544-byte OAM block moved, not duplicated. '
        'On-time/forced-blank entry gate retained, row cutoff246→249, final palette gate251 unchanged. '
        'Requires new full-envelope DMA and sprite qualification.'))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'])))


def replay(**args):
    original=replay_tool.patch
    try:
        replay_tool.patch=patch
        passed=replay_tool.replay(**args)
    finally: replay_tool.patch=original
    p=args['out']/'report.json';r=json.loads(p.read_text())
    r['row_scan_trial'].update(early_oam=True,row_cutoff=249)
    r['sources'][str(Path(__file__))]=sha(Path(__file__))
    r['scope']=(__doc__+' Cross-ROM admission pins complete original cartridge and exact patch. '
        'Same-ROM uninterrupted video/state/input/native PCM control and all initial CPU/WRAM/VRAM equality required. '
        'Restored trace clocks are not used. All later differences retained. DMA safety not established by this replay.')
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
