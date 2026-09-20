"""Ablate camera pre-service; retain normal IRQ, recovery and pending ownership."""
import argparse
import json
from pathlib import Path
import shutil
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

PARENT_SHA = 'f6f69215716ecc077c9082da0a20db1eaaa064daab81b0992a54cade834d1e16'


def patch(data):
    image = bytearray(data)
    for bank in range(1, 9):
        at = bank * 65536 + 0x7be0
        if image[at:at+20] != bytes.fromhex('9c00420848ada31cd00568284c5f3268284c807b'):
            raise ValueError('Changed camera pre-service entry')
        # Retain the late-edge wait at7E00 and STZ4200. Jump directly to
        # the original camera continuation without touching pending or registers.
        image[at+3:at+6] = bytes.fromhex('4c5f32')
    checksum(image)
    return image


def build(parent, out):
    rom = parent / 'native-cpu.sfc'
    if out.exists() or sha(rom) != PARENT_SHA:
        raise ValueError('Exact3955 and fresh output required')
    image = patch(rom.read_bytes())
    out.mkdir()
    for p in parent.iterdir():
        if p.is_file():
            shutil.copyfile(p, out / p.name)
    (out / 'native-cpu.sfc').write_bytes(image)
    meta = json.loads((parent / 'manifest.json').read_text())
    paths = [Path(__file__), Path('tests/test_audio_regular_irq.py'),
             Path('tools/build_inline_pitch_trial.py'), rom, parent / 'manifest.json']
    meta.update(rom_sha256=sha(out / 'native-cpu.sfc'), experimental_audio_regular_irq=dict(
        sources={str(p): sha(p) for p in paths}, scope=__doc__,
        camera_pre_service_disabled=True, release_ready=False))
    (out / 'manifest.json').write_text(json.dumps(meta, indent=2) + '\n')
    print(json.dumps(dict(out=str(out), rom_sha256=meta['rom_sha256'])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for k in ('parent', 'out'):
        p.add_argument('--' + k, type=Path, required=True)
    build(**vars(p.parse_args()))
