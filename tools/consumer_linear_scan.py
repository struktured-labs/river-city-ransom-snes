"""Unroll empty consumer suffix searches; preserve queue order, budgets and deadlines."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from tools import early_oam_chr_slack as replay_tool
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

PARENT_SHA = '635f21cd2f7951dd3e8acf07fabfb8acdc68302518f1bdb942a3a3fd8d4c71e3'
SITE = 0x839e
HELPER = 0x7380
LIMIT = 0x480
compose_parent = replay_tool.composed


def assemble():
    with tempfile.TemporaryDirectory(prefix='rcr-consumer-linear-') as temp:
        obj = Path(temp)/'helper.o'; binary = Path(temp)/'helper.bin'
        subprocess.run(['.deps/cc65/bin/ca65','-o',str(obj),'snes/consumer_linear_scan.asm'],check=True)
        subprocess.run(['.deps/cc65/bin/ld65','-C','snes/consumer_linear_scan.cfg','-o',str(binary),str(obj)],check=True)
        return binary.read_bytes()


def patch(image,helper):
    if hashlib.sha256(image).hexdigest() != PARENT_SHA: raise ValueError('Need exact CHR-restored3527 parent')
    if image[SITE:SITE+7] != bytes.fromhex('e220e07900b032'): raise ValueError('Changed consumer entry')
    if image[HELPER:HELPER+LIMIT] != b'\xff'*LIMIT or not 0 < len(helper) <= LIMIT:
        raise ValueError('Occupied or oversized helper')
    data = bytearray(image); data[SITE:SITE+5] = bytes.fromhex('4c8073eaea')
    data[HELPER:HELPER+len(helper)] = helper; checksum(data)
    changes = [i for i,(a,b) in enumerate(zip(image,data)) if a != b]
    if any(not(SITE <= i < SITE+5 or HELPER <= i < HELPER+len(helper) or 0xffdc <= i < 0xffe0) for i in changes):
        raise ValueError('Unrelated change')
    return bytes(data),changes


def build(parent,out):
    if out.exists(): raise ValueError('Fresh output required')
    meta = json.loads((parent/'manifest.json').read_text())
    if sha(parent/'native-cpu.sfc') != meta['rom_sha256']: raise ValueError('Changed parent manifest')
    helper = assemble(); image,changes = patch((parent/'native-cpu.sfc').read_bytes(),helper)
    paths = [Path(__file__),Path('snes/consumer_linear_scan.asm'),Path('snes/consumer_linear_scan.cfg'),
             Path('tools/build_inline_pitch_trial.py'),Path('.deps/cc65/bin/ca65'),Path('.deps/cc65/bin/ld65'),
             parent/'native-cpu.sfc',parent/'manifest.json']
    out.mkdir()
    for p in parent.iterdir():
        if p.is_file(): shutil.copy2(p,out/p.name)
    (out/'native-cpu.sfc').write_bytes(image); (out/'consumer-linear.bin').write_bytes(helper)
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_consumer_linear_scan=dict(
        sources={str(p):sha(p) for p in paths},changed_offsets=changes,helper_hex=helper.hex(),release_ready=False,
        scope=__doc__+' No new state/cache or priority. Unrolled BIT tests only inside the bounded suffix; '
        'odd starts/insufficient budgets use original code. DP1C is existing beam scratch. '
        'No producer, CHR246/row249/palette254, OAM or audio changes.'))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'],helper_bytes=len(helper))))


def replay(**args):
    meta = json.loads((args['trial']/'manifest.json').read_text())['experimental_consumer_linear_scan']
    if any(sha(Path(p)) != h for p,h in meta['sources'].items()): raise ValueError('Changed consumer dependencies')
    def composed(image):
        parent,_ = compose_parent(image)
        return patch(parent,assemble())
    original = replay_tool.composed
    try:
        replay_tool.composed = composed
        valid = replay_tool.replay(**args)
    finally: replay_tool.composed = original
    p = args['out']/'report.json'; report = json.loads(p.read_text())
    report['sources'].update(meta['sources']); report['sources'][str(Path(__file__))] = sha(Path(__file__))
    report['row_scan_trial']['consumer_linear_scan'] = True
    report['scope'] = __doc__+' Guarded composition from3408 with identical initial fullCPU/WRAM/VRAM. '
    report['scope'] += 'All primary differences retained; not boot, DMA, original-speed or audio qualification.'
    p.write_text(json.dumps(report,indent=2)+'\n')
    return valid


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); s = p.add_subparsers(dest='mode',required=True)
    b = s.add_parser('build'); r = s.add_parser('replay')
    for k in ('parent','out'): b.add_argument('--'+k,type=Path,required=True)
    for k in ('core','candidate','normal','checkpoint-report','out','trial','resume-control'):
        r.add_argument('--'+k,type=Path,required=True)
    for k in ('frame','frames'): r.add_argument('--'+k,type=int,required=True)
    args = vars(p.parse_args()); mode = args.pop('mode')
    if mode == 'build': build(**args)
    else: raise SystemExit(0 if replay(**args) else 1)
