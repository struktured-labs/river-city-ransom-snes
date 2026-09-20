"""Require a preloaded empty SRAM seed instead of executing a boot initializer."""
import argparse
import json
from pathlib import Path
import shutil
import struct

from tools.audio_packet_log import labels
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.run_seeded_sram import seed_bytes
import hashlib


def build(parent, out):
    manifest = json.loads((parent / 'manifest.json').read_text())
    rom = parent / 'native-cpu.sfc'
    if sha(rom) != manifest['rom_sha256']:
        raise ValueError('Parent differs')
    for name, digest in manifest['diagnostic_packet_log']['sources'].items():
        if sha(Path(name)) != digest:
            raise ValueError('Parent source changed: ' + name)
    image = bytearray(rom.read_bytes())
    old = bytes.fromhex('2000e0')
    if image[0x8000:0x8100].count(old) != 1:
        raise ValueError('Need original upload-wrapper call')
    symbols = labels(parent / 'native_boot.lbl')
    at = image.index(old, 0x8000, 0x8100)
    image[at:at + 3] = b'\x20' + struct.pack('<H', symbols['spc_upload'])
    checksum(image)
    out.mkdir(parents=True, exist_ok=False)
    (out / 'native-cpu.sfc').write_bytes(image)
    for name in ('native_boot.lbl', 'native_runtime.lbl', 'logger.lbl', 'logger.bin', 'gate.lbl', 'gate.bin'):
        if (parent / name).exists():
            shutil.copyfile(parent / name, out / name)
    sources = (Path(__file__), Path('tools/run_seeded_sram.py'), Path('tools/build_inline_pitch_trial.py'),
               parent / 'manifest.json', rom, parent / 'native_boot.lbl')
    manifest.update(rom_sha256=sha(out / 'native-cpu.sfc'), diagnostic_packet_log=dict(
        requires_sram_seed_sha256=hashlib.sha256(seed_bytes()).hexdigest(), default_enabled=False,
        deployed=False, scope=__doc__, sources={str(p): sha(p) for p in sources},
        parent_logger=manifest['diagnostic_packet_log']))
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(dict(sha256=manifest['rom_sha256'])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    build(**vars(p.parse_args()))
