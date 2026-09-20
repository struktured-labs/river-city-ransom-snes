"""Earlier main work with camera publication only after the current street scan.

Offline experiment: do not publish camera writes before line30 directly into
the already-started frame. The unchanged VBlank publisher consumes the committed
camera instead. No new wait, timer, graphics producer, or audio code is added.
Actual input/store-to-display latency must be compared, not inferred from this.
"""
import argparse
import json
from pathlib import Path
import shutil

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_retained_producer_guard import symbols

BODY = bytes.fromhex('ad3f21ad3721ad3d2148ad3d212901d00b68c91e9007c9c29017800168'
                     'a5f68d941c8d971ca53d29018d951c8d981c38601860')


def patch(image, start):
    if len(image) != 0x200000 or not 0x2000 < start < 0x4000:
        raise ValueError('Wrong cartridge/helper address')
    changed = bytearray(image)
    sites = []
    for bank in range(1, 9):
        at = bank*65536+start
        if image[at:at+len(BODY)] != BODY:
            raise ValueError('Different camera policy/ABI')
        site = at+BODY.index(bytes.fromhex('c91e9007'))+1
        changed[site] = 0
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
        raise ValueError('Need authenticated earlier-main candidate')
    spec = meta['experimental_main_phase_reprobe']
    for name, digest in spec['sources'].items():
        if sha(Path(name)) != digest:
            raise ValueError('Changed earlier-main source')
    start = symbols(parent/'native_runtime.lbl')['camera_publish_safe']
    changed, sites = patch(rom.read_bytes(), start)
    out.mkdir(parents=True)
    for source in parent.iterdir():
        if source.is_file():
            shutil.copy2(source, out/source.name)
    (out/'native-cpu.sfc').write_bytes(changed)
    paths = [Path(__file__), Path('tools/build_inline_pitch_trial.py'),
             Path('tools/build_retained_producer_guard.py'),
             Path('snes/camera_publish_safe.inc'), rom, parent/'manifest.json',
             parent/'native_runtime.lbl']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),
                experimental_phase_camera=dict(parent=str(parent), sites=sites,
                    start=start, size=len(BODY), early_cutoff=0, late_cutoff=194,
                    sources={str(p):sha(p) for p in paths}, scope=__doc__,
                    release_ready=False, latency_verified=False))
    (out/'manifest.json').write_text(json.dumps(meta, indent=2)+'\n')
    print(json.dumps(dict(out=str(out), rom_sha256=meta['rom_sha256'])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):
        p.add_argument('--'+name, type=Path, required=True)
    build(**vars(p.parse_args()))
