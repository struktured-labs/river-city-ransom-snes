"""Give the fused sprite build sixteen scanlines more retained-interrupt margin."""
import argparse
import json
from pathlib import Path
import shutil

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_main_phase_trial import SIZE
from tools.build_retained_producer_guard import symbols


def patch(image, start):
    if len(image) != 0x200000 or not 0x2000 < start < 0x4000:
        raise ValueError('Wrong ROM or phase helper')
    body = image[65536+start:65536+start+SIZE]
    needle = bytes.fromhex('c96090')
    if body[:3] != bytes.fromhex('084820') or body[-3:] != bytes.fromhex('606860') or body.count(needle) != 1:
        raise ValueError('Need unchanged phase96 helper')
    result = bytearray(image)
    sites = []
    for bank in range(1,9):
        at = bank*65536+start
        if image[at:at+SIZE] != body:
            raise ValueError('Different mirror')
        site = at+body.index(needle)+1
        sites.append(site)
        result[site] = 80
    checksum(result)
    allowed = set(sites) | set(range(0xffdc,0xffe0))
    if any(i not in allowed for i,(a,b) in enumerate(zip(image,result)) if a != b):
        raise ValueError('Unrelated mutation')
    return bytes(result),sites


def build(parent, out):
    if out.exists():
        raise ValueError('Fresh candidate required')
    meta = json.loads((parent/'manifest.json').read_text())
    rom = parent/'native-cpu.sfc'
    if (sha(rom) != meta['rom_sha256'] or meta['experimental_main_phase_line'] != 96 or
            not meta.get('experimental_sprite_fused_copy')):
        raise ValueError('Need bound fused phase96 parent')
    image, sites = patch(rom.read_bytes(),symbols(parent/'native_runtime.lbl')['gameplay_phase_start'])
    out.mkdir()
    for p in parent.iterdir():
        if p.is_file():shutil.copy2(p,out/p.name)
    (out/'native-cpu.sfc').write_bytes(image)
    paths = [Path(__file__),Path('tools/build_inline_pitch_trial.py'),Path('tools/build_main_phase_trial.py'),
             Path('tools/build_retained_producer_guard.py'),rom,parent/'manifest.json',parent/'native_runtime.lbl']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_main_phase_line=80,
                experimental_fused_phase80=dict(parent=str(parent),sites=sites,
                    sources={str(p):sha(p) for p in paths},release_ready=False,
                    scope=__doc__+' Only eight compare operands and checksum change. '
                          'Earlier phase64 had scrolling failures; no inherited scrolling acceptance.'))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'])))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):p.add_argument('--'+k,type=Path,required=True)
    build(**vars(p.parse_args()))
