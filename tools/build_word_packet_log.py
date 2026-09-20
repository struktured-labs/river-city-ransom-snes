"""Replace a bound diagnostic logger with word-copy/folded-XOR implementation."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.audio_packet_log import labels
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum


def build(parent, out):
    manifest = json.loads((parent / 'manifest.json').read_text())
    rom = parent / 'native-cpu.sfc'
    if sha(rom) != manifest['rom_sha256']:
        raise ValueError('Diagnostic parent identity differs')
    for name, digest in manifest['diagnostic_packet_log']['sources'].items():
        if sha(Path(name)) != digest:
            raise ValueError('Changed parent source: ' + name)
    before = (parent / 'logger.bin').read_bytes()
    image = bytearray(rom.read_bytes())
    if image[0xE000:0xE000 + len(before)] != before or labels(parent / 'logger.lbl')['log_frame'] != 0xE080:
        raise ValueError('Diagnostic code differs')
    symbols = labels(parent / 'native_boot.lbl')
    out.mkdir(parents=True, exist_ok=False)
    subprocess.run(['.deps/cc65/bin/ca65', '-D', f'spc_frame={symbols["spc_frame"]}',
                    '--bin-include-dir', str(parent), '-o', str(out / 'logger.o'),
                    'snes/audio_packet_log_word.asm'], check=True)
    subprocess.run(['.deps/cc65/bin/ld65', '-C', 'snes/audio_packet_log.cfg',
                    '-Ln', str(out / 'logger.lbl'), '-o', str(out / 'logger.bin'),
                    str(out / 'logger.o')], check=True)
    after = (out / 'logger.bin').read_bytes()
    if len(after) > len(before) or after[:0x80] != before[:0x80]:
        raise ValueError('Expanded logger or changed upload wrapper')
    image[0xE000:0xE000 + len(before)] = after + b'\xff' * (len(before) - len(after))
    checksum(image)
    (out / 'native-cpu.sfc').write_bytes(image)
    for name in ('native_boot.lbl', 'native_runtime.lbl'):
        shutil.copyfile(parent / name, out / name)
    paths = (Path(__file__), Path('snes/audio_packet_log_word.asm'), Path('snes/audio_packet_log.cfg'),
             Path('tools/build_inline_pitch_trial.py'), parent / 'manifest.json', rom,
             parent / 'logger.bin', parent / 'logger.lbl', parent / 'native_boot.lbl')
    manifest.update(rom_sha256=sha(out / 'native-cpu.sfc'), diagnostic_packet_log=dict(
        sources={str(p): sha(p) for p in paths}, default_enabled=False, deployed=False,
        logger_bytes=len(after), scope=__doc__))
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(dict(sha256=manifest['rom_sha256'], logger_bytes=len(after),
                         labels=labels(out / 'logger.lbl'))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    build(**vars(p.parse_args()))
