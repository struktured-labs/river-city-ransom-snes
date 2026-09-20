"""Skip clean producer flag groups without changing row budgets or DMA deadlines."""
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
SITE = 0x8874
HELPER = 0x7380
compose_parent = replay_tool.composed


def assemble():
    with tempfile.TemporaryDirectory(prefix='rcr-producer-group-') as temp:
        obj = Path(temp)/'helper.o'; binary = Path(temp)/'helper.bin'
        subprocess.run(['.deps/cc65/bin/ca65', '-o', str(obj), 'snes/producer_group_scan.asm'], check=True)
        subprocess.run(['.deps/cc65/bin/ld65', '-C', 'snes/producer_group_scan.cfg', '-o', str(binary), str(obj)], check=True)
        return binary.read_bytes()


def patch(image, helper):
    if hashlib.sha256(image).hexdigest() != PARENT_SHA:
        raise ValueError('Need exact CHR-restored3527 parent')
    if image[SITE:SITE+7] != bytes.fromhex('bd001dc901f01a'):
        raise ValueError('Changed producer entry')
    if image[HELPER:HELPER+256] != b'\xff'*256 or not 0 < len(helper) <= 256:
        raise ValueError('Occupied or oversized helper')
    data = bytearray(image)
    data[SITE:SITE+5] = bytes.fromhex('4c8073eaea')
    data[HELPER:HELPER+len(helper)] = helper
    checksum(data)
    changes = [i for i,(a,b) in enumerate(zip(image,data)) if a != b]
    if any(not(SITE <= i < SITE+5 or HELPER <= i < HELPER+len(helper) or 0xffdc <= i < 0xffe0) for i in changes):
        raise ValueError('Unrelated change')
    return bytes(data), changes


def build(parent, out):
    if out.exists(): raise ValueError('Fresh output required')
    meta = json.loads((parent/'manifest.json').read_text())
    if sha(parent/'native-cpu.sfc') != meta['rom_sha256']: raise ValueError('Changed parent manifest')
    helper = assemble(); image, changes = patch((parent/'native-cpu.sfc').read_bytes(), helper)
    paths = [Path(__file__), Path('snes/producer_group_scan.asm'), Path('snes/producer_group_scan.cfg'),
             Path('tools/build_inline_pitch_trial.py'), Path('.deps/cc65/bin/ca65'), Path('.deps/cc65/bin/ld65'),
             parent/'native-cpu.sfc', parent/'manifest.json']
    out.mkdir()
    for p in parent.iterdir():
        if p.is_file(): shutil.copy2(p, out/p.name)
    (out/'native-cpu.sfc').write_bytes(image); (out/'producer-group.bin').write_bytes(helper)
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'), experimental_producer_group_scan=dict(
        sources={str(p):sha(p) for p in paths}, changed_offsets=changes, helper_hex=helper.hex(),
        release_ready=False, scope=__doc__+' No ready staging overwrite or ring/budget boundary crossing. '
        'Original row conversion, CHR246/row249/palette254 admission, OAM and audio code unchanged. '
        'Earlier grouped producer experiment regressed an old route; this exact cartridge needs fresh qualification.'))
    (out/'manifest.json').write_text(json.dumps(meta, indent=2)+'\n')
    print(json.dumps(dict(out=str(out), rom_sha256=meta['rom_sha256'], helper_bytes=len(helper))))


def replay(**args):
    meta = json.loads((args['trial']/'manifest.json').read_text())['experimental_producer_group_scan']
    if any(sha(Path(p)) != h for p,h in meta['sources'].items()): raise ValueError('Changed producer dependencies')
    def composed(image):
        parent,_ = compose_parent(image)
        return patch(parent, assemble())
    original = replay_tool.composed
    try:
        replay_tool.composed = composed
        valid = replay_tool.replay(**args)
    finally:
        replay_tool.composed = original
    p = args['out']/'report.json'; report = json.loads(p.read_text())
    report['sources'].update(meta['sources']); report['sources'][str(Path(__file__))] = sha(Path(__file__))
    report['row_scan_trial']['producer_group_scan'] = True
    report['scope'] = __doc__+' Exact guarded composition from3408 with identical initial fullCPU/WRAM/VRAM. '
    report['scope'] += 'All primary differences retained; not boot, DMA, original-speed or audio qualification.'
    p.write_text(json.dumps(report, indent=2)+'\n')
    return valid


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); s = p.add_subparsers(dest='mode', required=True)
    b = s.add_parser('build'); r = s.add_parser('replay')
    for k in ('parent','out'): b.add_argument('--'+k, type=Path, required=True)
    for k in ('core','candidate','normal','checkpoint-report','out','trial','resume-control'):
        r.add_argument('--'+k, type=Path, required=True)
    for k in ('frame','frames'): r.add_argument('--'+k, type=int, required=True)
    args = vars(p.parse_args()); mode = args.pop('mode')
    if mode == 'build': build(**args)
    else: raise SystemExit(0 if replay(**args) else 1)
