"""Phase96 with the tested post-street camera policy; offline qualification only."""
import argparse
import json
from pathlib import Path
import shutil

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_main_phase_trial import SIZE
from tools.build_phase_camera_trial import BODY
from tools.build_retained_producer_guard import symbols

PHASE = 96


def patch(image, start):
    if len(image) != 0x200000 or not 0x2000 < start < 0x4000:
        raise ValueError('Wrong cartridge/helper address')
    body = image[65536+start:65536+start+SIZE]
    needle = bytes((0xc9,64,0x90))
    if (body[:3] != bytes.fromhex('084820') or body[-3:] != bytes.fromhex('606860')
            or body.count(needle) != 1):
        raise ValueError('Different phase64 helper')
    changed = bytearray(image)
    sites = []
    for bank in range(1,9):
        at = bank*65536+start
        if image[at:at+SIZE] != body:
            raise ValueError('Different mirrored helper')
        site = at+body.index(needle)+1
        changed[site] = PHASE
        sites.append(site)
    checksum(changed)
    allowed = set(sites) | set(range(0xffdc,0xffe0))
    if any(i not in allowed for i,(a,b) in enumerate(zip(image,changed)) if a != b):
        raise ValueError('Unrelated cartridge change')
    return bytes(changed), sites


def build(parent, out):
    if out.exists():
        raise ValueError('Fresh output required')
    meta = json.loads((parent/'manifest.json').read_text())
    rom = parent/'native-cpu.sfc'
    if sha(rom) != meta['rom_sha256'] or meta['experimental_main_phase_line'] != 64:
        raise ValueError('Need authenticated phase64 parent')
    camera = meta['experimental_phase_camera']
    if camera['early_cutoff'] != 0 or camera['late_cutoff'] != 194:
        raise ValueError('Different camera policy')
    for name,digest in camera['sources'].items():
        if sha(Path(name)) != digest:
            raise ValueError('Changed camera patch source')
    labels = symbols(parent/'native_runtime.lbl')
    image = rom.read_bytes()
    expected_camera = BODY.replace(bytes.fromhex('c91e9007'),bytes.fromhex('c9009007'))
    for bank in range(1,9):
        at = bank*65536+labels['camera_publish_safe']
        if image[at:at+len(BODY)] != expected_camera:
            raise ValueError('Different production camera bytes')
    changed, sites = patch(image,labels['gameplay_phase_start'])
    out.mkdir(parents=True)
    for source in parent.iterdir():
        if source.is_file():
            shutil.copy2(source,out/source.name)
    (out/'native-cpu.sfc').write_bytes(changed)
    paths = [Path(__file__),Path('tools/build_inline_pitch_trial.py'),
             Path('tools/build_main_phase_trial.py'),Path('tools/build_phase_camera_trial.py'),
             Path('tools/build_retained_producer_guard.py'),Path('snes/main_phase.inc'),
             rom,parent/'manifest.json',parent/'native_runtime.lbl']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_main_phase_line=PHASE,
                experimental_phase_balance=dict(parent=str(parent),phase=PHASE,old_phase=64,
                    sites=sites,sources={str(p):sha(p) for p in paths},release_ready=False,
                    scope=__doc__+' Only eight main compare immediates and checksum change. '
                    'Historical phase/camera provenance remains under its original manifest keys.'))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):
        p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
