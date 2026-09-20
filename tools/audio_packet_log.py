"""Build/decode a diagnostic SRAM packet ring. Not a timing-neutral observer."""
import argparse
import json
from pathlib import Path
import shutil
import struct
import subprocess

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

MAGIC = b'RCRLOG01'
CAPACITY = 4095
SIZE = 131072


def decode(data):
    if len(data) != SIZE or data[:8] != MAGIC:
        raise ValueError('Missing exact 128 KiB RCRLOG01 SRAM')
    total = int.from_bytes(data[8:12], 'little')
    slot = 1 + total % CAPACITY
    expected = (0x6000 + (slot % 256) * 32, 0x20 + slot // 256)
    pointer = (int.from_bytes(data[12:14], 'little'), data[14])
    if pointer != expected:
        raise ValueError('Header pointer/count mismatch (possibly torn capture)')
    records = []
    for sequence in range(max(0, total - CAPACITY), total):
        slot = 1 + sequence % CAPACITY
        record = data[slot * 32:(slot + 1) * 32]
        check = 0
        for value in record[:31]:
            check ^= value
        if (record[31] != 0xA5 or check or
                int.from_bytes(record[:4], 'little') != sequence or record[6] not in (0, 1)):
            raise ValueError(f'Invalid/uncommitted packet {sequence}')
        records.append(dict(sequence=sequence, nmi=int.from_bytes(record[4:6], 'little'),
                            timeout=bool(record[6]), packet=record[7:30].hex()))
    return dict(total=total, overwritten=max(0, total - CAPACITY), records=records,
                scope='Gated CPU shadow after transfer; receiver bytes and physical time need independent validation.')


def labels(path):
    return {line.split()[2].lstrip('.'): int(line.split()[1], 16)
            for line in path.read_text().splitlines() if line.startswith('al ')}


def build(parent, out):
    manifest = json.loads((parent / 'manifest.json').read_text())
    rom = parent / 'native-cpu.sfc'
    if sha(rom) != manifest['rom_sha256']:
        raise ValueError('Parent ROM identity differs')
    symbols = labels(parent / 'native_boot.lbl')
    source_paths = [Path(__file__), Path('snes/audio_packet_log.asm'),
                    Path('snes/audio_packet_log.cfg'), parent / 'native_boot.lbl',
                    parent / 'manifest.json', rom]
    sources = {str(p): sha(p) for p in source_paths}
    image = bytearray(rom.read_bytes())
    if image[0xFFD5:0xFFD9] != bytes.fromhex('31000b00'):
        raise ValueError('Expected SRAM-free Fast HiROM parent')
    out.mkdir(parents=True, exist_ok=False)
    subprocess.run(['.deps/cc65/bin/ca65', '-D', f'spc_frame={symbols["spc_frame"]}',
                    '-D', f'spc_upload={symbols["spc_upload"]}',
                    '-o', str(out / 'logger.o'), 'snes/audio_packet_log.asm'], check=True)
    subprocess.run(['.deps/cc65/bin/ld65', '-C', 'snes/audio_packet_log.cfg',
                    '-Ln', str(out / 'logger.lbl'), '-o', str(out / 'logger.bin'),
                    str(out / 'logger.o')], check=True)
    code = (out / 'logger.bin').read_bytes()
    if image[0xE000:0xE000 + len(code)] != b'\xff' * len(code):
        raise ValueError('Logger ROM padding occupied')
    linked = labels(out / 'logger.lbl')
    changes = []
    for original, replacement, begin, end in (
            ('spc_upload', 'log_upload', symbols['reset'], symbols['reset'] + 0x100),
            ('spc_frame', 'log_frame', symbols['audio_publish_bridge'], symbols['audio_publish_bridge'] + 0x80)):
        call = b'\x20' + struct.pack('<H', symbols[original])
        if image[begin:end].count(call) != 1:
            raise ValueError('Expected unique bridge JSR: ' + original)
        at = image.index(call, begin, end)
        new = b'\x20' + struct.pack('<H', linked[replacement])
        image[at:at + 3] = new
        changes.append(dict(offset=at, before=call.hex(), after=new.hex()))
    image[0xE000:0xE000 + len(code)] = code
    image[0xFFD6] = 2            # ROM + RAM + battery; diagnostic save name only
    image[0xFFD8] = 7            # 128 KiB, banks20..2f:6000..7fff
    checksum(image)
    (out / 'native-cpu.sfc').write_bytes(image)
    for name in ('native_boot.lbl', 'native_runtime.lbl'):
        shutil.copyfile(parent / name, out / name)
    manifest.update(rom_sha256=sha(out / 'native-cpu.sfc'), diagnostic_packet_log=dict(
        default_enabled=False, sources=sources, changes=changes, logger_bytes=len(code),
        scope=__doc__, deployed=False))
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(dict(out=str(out), sha256=manifest['rom_sha256'])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    b = sub.add_parser('build')
    b.add_argument('--parent', type=Path, required=True)
    b.add_argument('--out', type=Path, required=True)
    d = sub.add_parser('decode')
    d.add_argument('sram', type=Path)
    args = parser.parse_args()
    if args.command == 'build':
        build(args.parent, args.out)
    else:
        print(json.dumps(decode(args.sram.read_bytes()), indent=2))
