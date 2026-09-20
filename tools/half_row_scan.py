"""Isolated 64-entry scan: test latency without the full scan or per-block beam-read cost."""
import argparse
import json
from pathlib import Path
import shutil

from tools import replay_row_scan_checkpoint as replay_tool
from tools.benchmark_report import sha
from tools.build_full_row_scan import patch as full_patch
from tools.build_inline_pitch_trial import checksum


def patch(image):
    data, _ = full_patch(image)
    data = bytearray(data); data[0x838e] = 64; checksum(data)
    return bytes(data), [i for i,(a,b) in enumerate(zip(image,data)) if a != b]


def build(parent, out):
    if out.exists(): raise ValueError('Fresh output required')
    image, changed = patch((parent/'native-cpu.sfc').read_bytes())
    meta = json.loads((parent/'manifest.json').read_text())
    if sha(parent/'native-cpu.sfc') != meta['rom_sha256']: raise ValueError('Changed parent')
    out.mkdir()
    for p in parent.iterdir():
        if p.is_file(): shutil.copy2(p,out/p.name)
    (out/'native-cpu.sfc').write_bytes(image)
    paths = [Path(__file__),Path('tools/build_full_row_scan.py'),Path('tools/build_inline_pitch_trial.py'),
             parent/'native-cpu.sfc',parent/'manifest.json']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'), experimental_full_row_scan=dict(
        sources={str(p):sha(p) for p in paths}, before=32, after=64, changed_offsets=changed,
        release_ready=False, scope=__doc__))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'])))


def replay(**args):
    original = replay_tool.patch
    try:
        replay_tool.patch = patch
        passed = replay_tool.replay(**args)
    finally:
        replay_tool.patch = original
    p = args['out']/'report.json'; r = json.loads(p.read_text())
    r['row_scan_trial']['after'] = 64
    r['scope'] = (__doc__+' Exact pinned parent, one limit operand and checksum only. '
        'Same-ROM uninterrupted video/state/input/native PCM control and full initial CPU/WRAM/VRAM equality required. '
        'All later differences retained; no trial equality or release claim.')
    r['sources'][str(Path(__file__))] = sha(Path(__file__))
    p.write_text(json.dumps(r,indent=2)+'\n')
    return passed


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); subs=p.add_subparsers(dest='mode',required=True)
    b=subs.add_parser('build'); r=subs.add_parser('replay')
    for k in ('parent','out'): b.add_argument('--'+k,type=Path,required=True)
    for k in ('core','candidate','normal','checkpoint-report','out','trial','resume-control'):
        r.add_argument('--'+k,type=Path,required=True)
    for k in ('frame','frames'): r.add_argument('--'+k,type=int,required=True)
    args=vars(p.parse_args()); mode=args.pop('mode')
    if mode=='build': build(**args)
    else: raise SystemExit(0 if replay(**args) else 1)
