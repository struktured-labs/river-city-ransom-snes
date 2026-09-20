"""Export diagnostic SRAM in-process before the libretro core unloads it."""
import argparse
import ctypes as C
import json
from pathlib import Path

from tools import smoke_libretro
from tools.audio_packet_log import decode, SIZE
from tools.benchmark_report import sha


def capture(core, rom, out, frames=5000):
    out.mkdir(parents=True, exist_ok=False)
    original = C.CDLL
    observations = []

    def load(*args, **kwargs):
        library = original(*args, **kwargs)
        unload = library.retro_unload_game
        run = library.retro_run

        def snapshot():
            size = library.retro_get_memory_size(0)
            ptr = library.retro_get_memory_data(0)
            if not ptr or size != SIZE:
                raise ValueError('Core does not expose 128 KiB SRAM')
            return C.string_at(ptr, size)

        def step():
            run()
            data = snapshot()
            ptr = library.retro_get_memory_data(2)
            ram = C.string_at(ptr, library.retro_get_memory_size(2))
            observations.append(dict(frame=len(observations), initialized=data[:8] == b'RCRLOG01',
                total=int.from_bytes(data[8:12], 'little'),
                nmi=int.from_bytes(ram[0x1C04:0x1C06], 'little'),
                faults=list(ram[0x1C06:0x1C0C])))

        def finish():
            try:
                data = snapshot()
                (out / 'packets.srm').write_bytes(data)
                (out / 'frames.json').write_text(json.dumps(observations, indent=2) + '\n')
                try:
                    result = decode(data)
                except ValueError as error:
                    result = dict(status='invalid', error=str(error))
                (out / 'packets.json').write_text(json.dumps(result, indent=2) + '\n')
            finally:
                unload()
        library.retro_run = step
        library.retro_unload_game = finish
        return library

    C.CDLL = load
    try:
        # The logo runs before native WRAM initialization; native smoke's fixed
        # frame-300 assertion is not valid for this cartridge's splash duration.
        receipt = smoke_libretro.run(core, rom, frames, out / 'audio.wav', 'render',
            out / 'last.png', out / 'ram.bin', 'walk')
    finally:
        C.CDLL = original
    receipt['sources'] = {str(p): sha(p) for p in (Path(__file__),
        Path('tools/audio_packet_log.py'), Path('tools/smoke_libretro.py'), core, rom)}
    receipt['scope'] = __doc__ + ' Logger adds CPU time. No physical audio correlation yet.'
    decoded = decode((out / 'packets.srm').read_bytes())
    live = [o for o in observations if o['initialized'] and o['total'] > 0]
    receipt['native_fault_frames'] = [o['frame'] for o in live
        if o['faults'][0] or o['faults'][5] or o['faults'][4] > 1]
    receipt['logged_packets'] = decoded['total']
    receipt['status'] = 'passed' if live and not receipt['native_fault_frames'] else 'failed'
    (out / 'report.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('core', 'rom', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--frames', type=int, default=5000)
    capture(**vars(parser.parse_args()))
