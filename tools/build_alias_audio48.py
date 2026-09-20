"""Test phase48 on exact ready-alias3890; retain camera-boundary and ownership guards."""
import argparse
import json
from pathlib import Path
import shutil
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

PARENT_SHA = '67fa19ee60b76af7c8e7ec581075eabb97efb19e7ce933e2cc34db66882cbda2'
PATTERNS = ((0x7849, bytes.fromhex('a9508d0942')), (0x78cf, bytes.fromhex('e0509007')))


def patch(data):
    image = bytearray(data)
    sites = []
    for bank in range(1, 9):
        for offset, expected in PATTERNS:
            at = bank * 65536 + offset
            if image[at:at+len(expected)] != expected:
                raise ValueError('Changed timer/recovery instruction')
            image[at+1] = 48
            sites.append(at+1)
    checksum(image)
    return image, sites


def build(parent, out):
    rom = parent/'native-cpu.sfc'
    if out.exists() or sha(rom) != PARENT_SHA:
        raise ValueError('Exact3890 and fresh output required')
    image, sites = patch(rom.read_bytes())
    out.mkdir()
    for p in parent.iterdir():
        if p.is_file(): shutil.copyfile(p, out/p.name)
    (out/'native-cpu.sfc').write_bytes(image)
    meta = json.loads((parent/'manifest.json').read_text())
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'), experimental_alias_audio48=dict(
        sites=sites, old=80, new=48, release_ready=False,
        sources={str(p):sha(p) for p in (Path(__file__), Path('tools/build_inline_pitch_trial.py'),
                                       rom, parent/'manifest.json')}))
    (out/'manifest.json').write_text(json.dumps(meta, indent=2)+'\n')
    print(json.dumps(dict(out=str(out), rom_sha256=meta['rom_sha256'])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'): p.add_argument('--'+k, type=Path, required=True)
    build(**vars(p.parse_args()))
