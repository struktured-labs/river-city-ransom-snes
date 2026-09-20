"""Move diagnostic header initialization into a pre-existing splash wait interval."""
import argparse
import json
from pathlib import Path
import shutil
import struct
import subprocess

from tools.audio_packet_log import labels
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum


def build(parent, out):
    manifest = json.loads((parent / 'manifest.json').read_text())
    rom = parent / 'native-cpu.sfc'
    if sha(rom) != manifest['rom_sha256']:
        raise ValueError('Parent differs')
    for p, h in manifest['diagnostic_packet_log']['sources'].items():
        if sha(Path(p)) != h:
            raise ValueError('Changed parent dependency: ' + p)
    image = bytearray(rom.read_bytes())
    marker = bytes.fromhex('a9018df01f9cf11f20')
    bank = bytes(image[0x110000:0x111000])
    if bank.count(marker) != 1:
        raise ValueError('Need unique first splash VBlank call')
    at = 0x110000 + bank.index(marker) + len(marker) - 1
    wait = int.from_bytes(image[at + 1:at + 3], 'little')
    if image[0x110000 + wait:0x110000 + wait + 11] != bytes.fromhex('ad124230fbad124210fb60'):
        raise ValueError('Unexpected VBlank routine')
    symbols = labels(parent / 'native_boot.lbl')
    old = bytes.fromhex('2000e0')
    if image[0x8000:0x8100].count(old) != 1:
        raise ValueError('Need unique old upload wrapper call')
    boot_call = image.index(old, 0x8000, 0x8100)
    out.mkdir(parents=True, exist_ok=False)
    subprocess.run(['.deps/cc65/bin/ca65', '-D', f'next_vblank={wait}',
        '-o', str(out / 'initializer.o'), 'snes/audio_packet_log_splash.asm'], check=True)
    subprocess.run(['.deps/cc65/bin/ld65', '-C', 'snes/audio_packet_log_splash.cfg',
        '-o', str(out / 'initializer.bin'), str(out / 'initializer.o')], check=True)
    code = (out / 'initializer.bin').read_bytes()
    if image[0x110E00:0x110E00 + len(code)] != b'\xff' * len(code):
        raise ValueError('Initializer padding occupied')
    image[at:at + 3] = bytes.fromhex('20000e')
    image[boot_call:boot_call + 3] = b'\x20' + struct.pack('<H', symbols['spc_upload'])
    image[0x110E00:0x110E00 + len(code)] = code
    checksum(image)
    (out / 'native-cpu.sfc').write_bytes(image)
    for name in ('native_boot.lbl', 'native_runtime.lbl', 'logger.lbl', 'logger.bin', 'gate.lbl', 'gate.bin'):
        if (parent / name).exists():
            shutil.copyfile(parent / name, out / name)
    sources = (Path(__file__), Path('snes/audio_packet_log_splash.asm'),
        Path('snes/audio_packet_log_splash.cfg'), Path('tools/build_inline_pitch_trial.py'),
        parent / 'manifest.json', rom, parent / 'native_boot.lbl')
    manifest.update(rom_sha256=sha(out / 'native-cpu.sfc'), diagnostic_packet_log=dict(
        default_enabled=False, deployed=False, scope=__doc__,
        sources={str(p): sha(p) for p in sources}, parent_logger=manifest['diagnostic_packet_log'],
        startup=dict(splash_call_rom_offset=at, original_wait=wait, restored_upload_call=boot_call,
                     initializer_bytes=len(code))))
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(dict(sha256=manifest['rom_sha256'], bytes=len(code), wait=wait)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    build(**vars(p.parse_args()))
