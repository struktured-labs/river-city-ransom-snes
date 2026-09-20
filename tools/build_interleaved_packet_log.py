"""Diagnostic-only sender that writes SRAM during paired-port acknowledgement waits."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.audio_packet_log import labels
from tools.benchmark_report import sha
from tools.build_bridge_packet_log import BRIDGE
from tools.build_inline_pitch_trial import checksum


def build(parent, out):
    manifest = json.loads((parent / 'manifest.json').read_text())
    rom = parent / 'native-cpu.sfc'
    if sha(rom) != manifest['rom_sha256']:
        raise ValueError('Parent differs')
    for name, digest in manifest['diagnostic_packet_log']['sources'].items():
        if sha(Path(name)) != digest:
            raise ValueError('Changed parent source: ' + name)
    image = bytearray(rom.read_bytes())
    symbols = labels(parent / 'native_boot.lbl')
    bridge = symbols['audio_publish_bridge']
    if image[bridge:bridge + len(BRIDGE)] != BRIDGE:
        raise ValueError('Wrong gated paired-packet bridge')
    before = (parent / 'logger.bin').read_bytes()
    if image[0xE000:0xE000 + len(before)] != before or len(before) != 559:
        raise ValueError('Need original logger preimage')
    out.mkdir(parents=True, exist_ok=False)
    subprocess.run(['.deps/cc65/bin/ca65', '--bin-include-dir', str(parent),
        '-o', str(out / 'logger.o'), 'snes/audio_packet_log_interleaved.asm'], check=True)
    subprocess.run(['.deps/cc65/bin/ld65', '-C', 'snes/audio_packet_log.cfg',
        '-Ln', str(out / 'logger.lbl'), '-o', str(out / 'logger.bin'), str(out / 'logger.o')], check=True)
    after = (out / 'logger.bin').read_bytes()
    if after[:0x80] != before[:0x80] or image[0xE000 + len(before):0xE000 + len(after)] != b'\xff' * (len(after) - len(before)):
        raise ValueError('Changed boot wrapper or occupied padding')
    image[0xE000:0xE000 + len(after)] = after
    checksum(image)
    (out / 'native-cpu.sfc').write_bytes(image)
    for name in ('native_boot.lbl', 'native_runtime.lbl'):
        shutil.copyfile(parent / name, out / name)
    sources = (Path(__file__), Path('snes/audio_packet_log_interleaved.asm'),
        Path('snes/audio_packet_log.cfg'), Path('tools/build_bridge_packet_log.py'),
        Path('tools/build_inline_pitch_trial.py'), parent / 'manifest.json', rom,
        parent / 'logger.bin', parent / 'native_boot.lbl')
    manifest.update(rom_sha256=sha(out / 'native-cpu.sfc'), diagnostic_packet_log=dict(
        default_enabled=False, deployed=False, logger_bytes=len(after), scope=__doc__,
        sources={str(p): sha(p) for p in sources},
        contract='Exact bridge only; A/X/Y scratch, DB restored, DP unchanged, A8/X16, C=timeout. '
                 'Timeout records may contain partial packet/old tail bytes and must never qualify.'))
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(dict(rom_sha256=manifest['rom_sha256'], bytes=len(after),
                         labels=labels(out / 'logger.lbl'))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    build(**vars(p.parse_args()))
