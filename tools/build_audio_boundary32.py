"""Park-entry trial: admit pending audio at line32 before masked camera work."""
import argparse
import json
from pathlib import Path
import shutil
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

PARENT_SHA = '7f65ee3ac50936bd6a6f9aefcfd8b9c00c02638a1f784bc77a7e7888e13dd90c'


def patch(image):
    image = bytearray(image)
    sites = []
    for bank in range(1, 9):
        at = bank * 65536 + 0x7bb4
        # Preserve both branches and the upper cutoff; do not change pending,
        # mapper ownership, depth, or NMI-enable guards.
        if image[at:at+8] != bytes.fromhex('e0309007e0f0b003'):
            raise ValueError('Changed camera eligibility checks')
        image[at+1] = 32
        sites.append(at+1)
    checksum(image)
    return image, sites


def build(parent, out):
    rom = parent / 'native-cpu.sfc'
    if out.exists() or sha(rom) != PARENT_SHA:
        raise ValueError('Exact3843 and fresh output required')
    image, sites = patch(rom.read_bytes())
    out.mkdir(parents=True)
    for p in parent.iterdir():
        if p.is_file():
            shutil.copyfile(p, out / p.name)
    (out / 'native-cpu.sfc').write_bytes(image)
    meta = json.loads((parent / 'manifest.json').read_text())
    meta.update(rom_sha256=sha(out / 'native-cpu.sfc'), experimental_audio_boundary32=dict(
        sites=sites, old=48, new=32, release_ready=False,
        sources={str(p): sha(p) for p in (Path(__file__),
            Path('tools/build_inline_pitch_trial.py'), rom, parent / 'manifest.json')}))
    (out / 'manifest.json').write_text(json.dumps(meta, indent=2) + '\n')
    print(json.dumps(dict(out=str(out), rom_sha256=meta['rom_sha256'])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for k in ('parent', 'out'):
        p.add_argument('--'+k, type=Path, required=True)
    build(**vars(p.parse_args()))
