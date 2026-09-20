"""Seed one explicitly selected libretro core; leave libc/other libraries alone."""
import argparse
from contextlib import contextmanager
import ctypes as C
import json
import os
from pathlib import Path
import runpy
import sys

from tools.benchmark_report import sha
from tools.run_seeded_sram import seed_bytes
from tools.smoke_libretro import Game


@contextmanager
def seeded_core(core_path, data, loaded):
    original = C.CDLL
    expected = core_path.resolve()

    def library(name, *args, **kwargs):
        core = original(name, *args, **kwargs)
        # Benchmark's renderer flush opens the process image via CDLL(None).
        # It is not a libretro core and must not be wrapped.
        if not isinstance(name, (str, bytes, os.PathLike)) or Path(os.fsdecode(name)).resolve() != expected:
            return core
        load = core.retro_load_game
        load.argtypes = [C.POINTER(Game)]
        load.restype = C.c_bool

        def load_game(game):
            result = load(game)
            if result:
                core.retro_get_memory_data.argtypes = [C.c_uint]
                core.retro_get_memory_data.restype = C.c_void_p
                core.retro_get_memory_size.argtypes = [C.c_uint]
                core.retro_get_memory_size.restype = C.c_size_t
                pointer = core.retro_get_memory_data(0)
                if not pointer or core.retro_get_memory_size(0) != len(data):
                    raise ValueError('Expected exact diagnostic SRAM mapping')
                C.memmove(pointer, data, len(data))
                if C.string_at(pointer, len(data)) != data:
                    raise ValueError('Seed readback differs')
                rom = Path(C.cast(game, C.POINTER(Game)).contents.path.decode()).resolve()
                loaded.append(dict(rom=str(rom), rom_sha256=sha(rom),
                                   core=str(expected), core_sha256=sha(expected)))
            return result
        core.retro_load_game = load_game
        return core

    C.CDLL = library
    try:
        yield
    finally:
        C.CDLL = original


def run(seed, receipt, command):
    if receipt.exists() or command.count('--core') != 1 or command.count('--rom') != 1:
        raise ValueError('Need fresh receipt and one explicit core/ROM')
    core = Path(command[command.index('--core') + 1]).resolve()
    rom = Path(command[command.index('--rom') + 1]).resolve()
    data = seed.read_bytes()
    if data != seed_bytes():
        raise ValueError('Need exact empty diagnostic SRAM seed')
    paths = (Path(__file__), Path('tools/run_seeded_sram.py'), Path('tools/smoke_libretro.py'),
             Path('tools/benchmark_capture.py'), seed, core, rom)
    sources = {str(p): sha(p) for p in paths}
    loaded = []
    previous = sys.argv
    try:
        with seeded_core(core, data, loaded):
            sys.argv = ['tools.benchmark_capture', *command]
            runpy.run_module('tools.benchmark_capture', run_name='__main__')
    finally:
        sys.argv = previous
    for path, digest in sources.items():
        if sha(Path(path)) != digest:
            raise ValueError('Changed source: ' + path)
    if loaded != [dict(rom=str(rom), rom_sha256=sha(rom), core=str(core), core_sha256=sha(core))]:
        raise ValueError('Expected exactly one selected game/core load')
    with receipt.open('x') as stream:
        json.dump(dict(loaded=loaded, seed_sha256=sha(seed), command=command, sources=sources,
            scope='Exact SRAM preload after load and before first run; selected core only. '
                  'No CPU/WRAM patch, skipped frame or state load. Physical loading not established.'),
                  stream, indent=2)
        stream.write('\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    run(args.seed, args.receipt, args.command[1:] if args.command[:1] == ['--'] else args.command)
