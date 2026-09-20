"""Load a diagnostic SRAM seed before the first emulated instruction; bind it explicitly."""
import argparse
import ctypes as C
import json
from pathlib import Path
import runpy
import sys

from tools.audio_packet_log import MAGIC, SIZE
from tools.benchmark_report import sha
from tools.smoke_libretro import Game


def seed_bytes():
    seed = bytearray(SIZE)
    seed[:8] = MAGIC
    seed[12:14] = (0x6020).to_bytes(2, 'little')
    seed[14] = 0x20
    return bytes(seed)


def run(seed, receipt, command):
    if receipt.exists() or not command or command[0] not in ('tools.benchmark_capture', 'tools.capture_audio_packet_log'):
        raise ValueError('Need fresh receipt and a supported capture module')
    data = seed.read_bytes()
    if data != seed_bytes():
        raise ValueError('Expected exact empty diagnostic SRAM seed')
    original = C.CDLL
    previous_argv = sys.argv
    loaded = []

    def library(*args, **kwargs):
        core = original(*args, **kwargs)
        load = core.retro_load_game
        load.argtypes = [C.POINTER(Game)]
        load.restype = C.c_bool

        def load_seed(game):
            result = load(game)
            if result:
                core.retro_get_memory_data.argtypes = [C.c_uint]
                core.retro_get_memory_data.restype = C.c_void_p
                core.retro_get_memory_size.argtypes = [C.c_uint]
                core.retro_get_memory_size.restype = C.c_size_t
                pointer = core.retro_get_memory_data(0)
                if not pointer or core.retro_get_memory_size(0) != SIZE:
                    raise ValueError('Expected 128 KiB mapped SRAM')
                C.memmove(pointer, data, SIZE)
                if C.string_at(pointer, SIZE) != data:
                    raise ValueError('SRAM seed readback differs')
                info = C.cast(game, C.POINTER(Game)).contents
                rom = Path(info.path.decode())
                loaded.append(dict(rom=str(rom), rom_sha256=sha(rom), core=str(args[0]), core_sha256=sha(Path(args[0]))))
            return result
        core.retro_load_game = load_seed
        return core

    C.CDLL = library
    try:
        sys.argv = command
        runpy.run_module(command[0], run_name='__main__')
    finally:
        C.CDLL = original
        sys.argv = previous_argv
    if len(loaded) != 1:
        raise ValueError('Expected one fresh seeded game')
    report = dict(loaded=loaded, seed_sha256=sha(seed), command=command,
        sources={str(p): sha(p) for p in (Path(__file__), Path('tools/smoke_libretro.py'),
            Path(command[0].replace('.', '/') + '.py'), seed)},
        scope='Explicit host SRAM initialization after retro_load_game, before first retro_run. '
              'No CPU/RAM/game-state patch, skipped frame, cycle change or saved-state load. '
              'This is a seeded cartridge setup, not a claim about physical SRAM loading.')
    receipt.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--write-seed', type=Path)
    p.add_argument('--seed', type=Path)
    p.add_argument('--receipt', type=Path)
    p.add_argument('command', nargs=argparse.REMAINDER)
    args = p.parse_args()
    if args.write_seed:
        if args.write_seed.exists():
            p.error('Seed output already exists')
        args.write_seed.write_bytes(seed_bytes())
    else:
        command = args.command[1:] if args.command[:1] == ['--'] else args.command
        if not args.seed or not args.receipt:
            p.error('Need seed and receipt')
        run(args.seed, args.receipt, command)
