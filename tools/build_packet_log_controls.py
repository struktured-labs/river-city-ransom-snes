"""Isolate SRAM mapping and boot initialization from runtime packet logging."""
import argparse
import json
from pathlib import Path
import shutil
import struct

from tools.audio_packet_log import labels
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum


def build(parent, out, mode):
    manifest = json.loads((parent / 'manifest.json').read_text())
    rom = parent / 'native-cpu.sfc'
    if sha(rom) != manifest['rom_sha256']:
        raise ValueError('Diagnostic parent differs')
    image = bytearray(rom.read_bytes())
    symbols = labels(parent / 'native_boot.lbl')
    start = symbols['audio_publish_bridge']
    old = bytes.fromhex('2080e0')
    if image[start:start + 128].count(old) != 1:
        raise ValueError('Need original continuous logger bridge')
    at = image.index(old, start, start + 128)
    image[at:at + 3] = b'\x20' + struct.pack('<H', symbols['spc_frame'])
    if mode == 'mapping-only':
        old = bytes.fromhex('2000e0')
        if image[0x8000:0x8100].count(old) != 1:
            raise ValueError('Missing boot logger wrapper')
        at = image.index(old, 0x8000, 0x8100)
        image[at:at + 3] = b'\x20' + struct.pack('<H', symbols['spc_upload'])
    elif mode != 'boot-only':
        raise ValueError('Unknown control mode')
    checksum(image)
    out.mkdir(parents=True, exist_ok=False)
    (out / 'native-cpu.sfc').write_bytes(image)
    for name in ('native_boot.lbl', 'native_runtime.lbl'):
        shutil.copyfile(parent / name, out / name)
    manifest.update(rom_sha256=sha(out / 'native-cpu.sfc'), packet_log_control=dict(
        mode=mode, deployed=False, sources={str(p): sha(p) for p in (Path(__file__),
            Path('tools/build_inline_pitch_trial.py'), parent / 'manifest.json', rom, parent / 'native_boot.lbl')}))
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(dict(mode=mode, sha256=manifest['rom_sha256'])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--mode', choices=('boot-only', 'mapping-only'), required=True)
    build(**vars(p.parse_args()))
