"""Replay a complete exported hardware episode with the exact embedded SPC engine.

Cold SPC state and VBlank scheduling are explicit experimental limitations;
this is not restoration of the hardware's internal DSP state or sub-frame timing.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha


def payload(records):
    if not records or len(records) * 24 > 65535:
        raise ValueError('Need nonempty single-bank episode')
    first = records[0]['sequence']
    previous = None
    stream = bytearray()
    for index, record in enumerate(records):
        if (record['sequence'] != first + index or record['timeout'] or
                not 0 <= record['nmi'] < 65536 or
                (previous is not None and (record['nmi'] - previous) & 65535 != 1)):
            raise ValueError('Need complete consecutive fault-free episode')
        packet = bytes.fromhex(record['packet'])
        if len(packet) != 23:
            raise ValueError('Incomplete packet')
        stream.extend(b'\x01' + packet)
        previous = record['nmi']
    return bytes(stream)


def build(candidate, episode, out):
    if out.exists():
        raise ValueError('Need fresh fixture path')
    report = bound_report(episode)
    manifest = json.loads((candidate / 'manifest.json').read_text())
    if sha(candidate / 'native-cpu.sfc') != manifest['rom_sha256']:
        raise ValueError('Cartridge bytes differ')
    if report['diagnostic_rom_sha256'] != manifest['rom_sha256'] or not report['physical_export_verified']:
        raise ValueError('Different/unverified physical cartridge')
    records = report['log']['records']
    stream = payload(records)
    image = (candidate / 'native-cpu.sfc').read_bytes()
    offset = manifest['sweep_driver_rom_offset']
    engine = image[offset:offset + manifest['sweep_driver_layout']['engine_bytes']]
    if hashlib.sha256(engine).hexdigest() != manifest['spc_sha256']:
        raise ValueError('Embedded engine differs')
    out.mkdir(parents=True, exist_ok=False)
    (out / 'stream.bin').write_bytes(stream)
    (out / 'engine.bin').write_bytes(engine)
    subprocess.run(['.deps/cc65/bin/ca65', '-g', '-I', 'snes',
        '-D', f'SOURCE_FRAMES={len(records)}', '-D', 'EXPERIMENTAL_SWEEP_EVENTS=1',
        '-D', f'SWEEP_DRIVER_BYTES={len(engine)}', '-D', 'AUDIO_PAIR=1', '-D', 'AUDIO_FAST_RESET=1',
        '-o', str(out / 'player.o'), 'snes/apu_packet_replay.asm'], check=True)
    subprocess.run(['.deps/cc65/bin/ld65', '-C', 'snes/native_boot.cfg',
        '-Ln', str(out / 'player.lbl'), '-o', str(out / 'player.bin'), str(out / 'player.o')], check=True)
    rom = bytearray(2097152)
    rom[0x8000:0x10000] = (out / 'player.bin').read_bytes()
    rom[0x120000:0x120000 + len(engine)] = engine
    rom[0x130000:0x130000 + len(stream)] = stream
    rom[0xffdc:0xffe0] = b'\xff\xff\0\0'
    total = sum(rom) & 65535
    struct.pack_into('<HH', rom, 0xffdc, total ^ 65535, total)
    (out / 'player.sfc').write_bytes(rom)
    paths = (Path(__file__), Path('snes/apu_packet_replay.asm'), Path('snes/native_audio.asm'),
             Path('snes/native_spc_frame.inc'), Path('snes/wram_clear.inc'), Path('snes/native_boot.cfg'),
             episode, candidate / 'manifest.json', candidate / 'native-cpu.sfc',
             out / 'stream.bin', out / 'engine.bin', out / 'player.sfc')
    result = dict(source_frames=len(records), packets=len(records), source_rom_sha256=manifest['rom_sha256'],
        rom_sha256=sha(out / 'player.sfc'), spc_sha256=sha(out / 'engine.bin'), mutation=None,
        first_physical_sequence=records[0]['sequence'], last_physical_sequence=records[-1]['sequence'],
        initial_spc_state='cold reset; not hardware state restoration',
        scheduling='one packet each VBlank; original sub-frame publication time unknown',
        sources={str(p): sha(p) for p in paths}, scope=__doc__, release_ready=False)
    (out / 'manifest.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(out=str(out), frames=len(records), sha256=result['rom_sha256'])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'episode', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    build(**vars(parser.parse_args()))
