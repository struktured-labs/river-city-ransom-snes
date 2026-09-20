"""Remove duplicate register saves only for the exact already-saving audio bridge."""
import argparse
import json
from pathlib import Path
import shutil

from tools.audio_packet_log import labels
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

BRIDGE = bytes.fromhex('0848da5a0b8b18fbc230a9001e5be220a90048abad150a48ada11c09f02d'
    '150a8d150a2080e0688d150a9005a9ee8d0b1ca9008d160a8d140ae23038fbab2b7afa68286b')
PREFIX = bytes.fromhex('20bcd208c22048da5ae2208b')
SUFFIX = bytes.fromhex('e220abc2207afa682860')


def trim(code, bridge):
    if bridge != BRIDGE or code[0x80:0x8C] != PREFIX or not code.endswith(SUFFIX):
        raise ValueError('Duplicate-save caller/prologue/epilogue contract differs')
    # The bound assembled body contains only relative control flow wholly
    # inside itself; its absolute/long operands are data, not code addresses.
    # Keep upload wrapper and log_frame entry unchanged. No production caller
    # other than this exact JSR may call this reduced-contract helper.
    return code[:0x80] + bytes.fromhex('20bcd2088b') + code[0x8C:-len(SUFFIX)] + bytes.fromhex('e220ab2860')


def build(parent, out):
    manifest = json.loads((parent / 'manifest.json').read_text())
    rom = parent / 'native-cpu.sfc'
    if sha(rom) != manifest['rom_sha256']:
        raise ValueError('Parent differs')
    for name, digest in manifest['diagnostic_packet_log']['sources'].items():
        if sha(Path(name)) != digest:
            raise ValueError('Changed parent dependency: ' + name)
    image = bytearray(rom.read_bytes())
    before = (parent / 'logger.bin').read_bytes()
    if image[0xE000:0xE000 + len(before)] != before:
        raise ValueError('Parent logger binary differs')
    symbols = labels(parent / 'native_boot.lbl')
    start = symbols['audio_publish_bridge']
    after = trim(before, image[start:start + len(BRIDGE)])
    image[0xE000:0xE000 + len(before)] = after + b'\xff' * (len(before) - len(after))
    checksum(image)
    out.mkdir(parents=True, exist_ok=False)
    (out / 'native-cpu.sfc').write_bytes(image)
    (out / 'logger.bin').write_bytes(after)
    (out / 'logger.lbl').write_text(f'al 00E080 .log_frame\nal {0xE000 + len(after) - 1:06X} .log_end\n')
    for name in ('native_boot.lbl', 'native_runtime.lbl'):
        shutil.copyfile(parent / name, out / name)
    paths = (Path(__file__), Path('tools/build_inline_pitch_trial.py'), parent / 'manifest.json',
             rom, parent / 'logger.bin', parent / 'native_boot.lbl')
    manifest.update(rom_sha256=sha(out / 'native-cpu.sfc'), diagnostic_packet_log=dict(
        default_enabled=False, deployed=False, logger_bytes=len(after),
        sources={str(p): sha(p) for p in paths}, scope=__doc__,
        contract='A/B/X/Y scratch, M8 X16 unchanged, P/DB/DP preserved. '
                 'Only exact audio bridge restores original caller state; not a general spc_frame wrapper.'))
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(dict(sha256=manifest['rom_sha256'], logger_bytes=len(after),
                         labels=labels(out / 'logger.lbl'))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    build(**vars(p.parse_args()))
