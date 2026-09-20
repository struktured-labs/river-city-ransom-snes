"""Fresh-process per-frame splash evidence; no emulator state or input writes."""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import struct
import wave

import numpy as np
from PIL import Image

try:
    from .smoke_libretro import Game, Variable, AVInfo
    from .benchmark_capture import decode_frame
except ImportError:
    from smoke_libretro import Game, Variable, AVInfo
    from benchmark_capture import decode_frame


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--core', type=Path, required=True)
    p.add_argument('--rom', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--frames', type=int, default=950)
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    core = C.CDLL(str(args.core.resolve()))
    fmt, latest, error = 0, None, []
    audio, chunk = bytearray(), bytearray()
    directory = str(args.out.resolve()).encode()

    @C.CFUNCTYPE(C.c_bool, C.c_uint, C.c_void_p)
    def env(cmd, data):
        nonlocal fmt
        if cmd in (9, 31):
            C.cast(data, C.POINTER(C.c_char_p))[0] = directory
            return True
        if cmd == 10:
            fmt = C.cast(data, C.POINTER(C.c_int))[0]
            return fmt in (0, 1, 2)
        if cmd in (3, 17):
            C.cast(data, C.POINTER(C.c_bool))[0] = cmd == 3
            return True
        if cmd == 15:
            var = C.cast(data, C.POINTER(Variable)).contents
            if var.key == b'snes9x_overscan':
                var.value = b'disabled'
                return True
        return False

    @C.CFUNCTYPE(None, C.c_void_p, C.c_uint, C.c_uint, C.c_size_t)
    def video(data, width, height, pitch):
        nonlocal latest
        try:
            if data:
                latest = decode_frame(C.string_at(data, pitch * height), width, height, pitch, fmt)
        except Exception as exc:
            error.append(str(exc))

    @C.CFUNCTYPE(None, C.c_int16, C.c_int16)
    def sample(l, r):
        chunk.extend(struct.pack('<hh', l, r))

    @C.CFUNCTYPE(C.c_size_t, C.POINTER(C.c_int16), C.c_size_t)
    def batch(data, count):
        chunk.extend(struct.pack(f'<{count*2}h', *data[:count*2]))
        return count

    @C.CFUNCTYPE(None)
    def poll():
        pass

    @C.CFUNCTYPE(C.c_int16, C.c_uint, C.c_uint, C.c_uint, C.c_uint)
    def buttons(port, device, index, ident):
        return 0

    for name, callback in [('environment', env), ('video_refresh', video),
                           ('audio_sample', sample), ('audio_sample_batch', batch),
                           ('input_poll', poll), ('input_state', buttons)]:
        fn = getattr(core, 'retro_set_' + name)
        fn.argtypes = [type(callback)]
        fn(callback)
    core.retro_load_game.argtypes = [C.POINTER(Game)]
    core.retro_load_game.restype = C.c_bool
    core.retro_get_memory_data.argtypes = [C.c_uint]
    core.retro_get_memory_data.restype = C.c_void_p
    core.retro_get_memory_size.argtypes = [C.c_uint]
    core.retro_get_memory_size.restype = C.c_size_t
    core.retro_get_system_av_info.argtypes = [C.POINTER(AVInfo)]
    core.retro_init()
    payload = args.rom.read_bytes()
    buf = C.create_string_buffer(payload)
    game = Game(str(args.rom.resolve()).encode(), C.cast(buf, C.c_void_p), len(payload), None)
    if not core.retro_load_game(C.byref(game)):
        raise RuntimeError('Core refused splash image')
    rows = []
    try:
        av = AVInfo()
        core.retro_get_system_av_info(C.byref(av))
        for frame in range(1, args.frames + 1):
            chunk.clear()
            core.retro_run()
            if error or latest is None:
                raise RuntimeError(error or 'Missing video')
            ram = C.string_at(core.retro_get_memory_data(2), core.retro_get_memory_size(2))
            vram = C.string_at(core.retro_get_memory_data(3), core.retro_get_memory_size(3))
            phase, edge = ram[0x1FF0:0x1FF2]
            filename = f'frame-{frame:05d}.png'
            if frame <= 300 or frame % 30 == 0 or phase in (1, 2, 3, 4, 5):
                Image.fromarray(latest).save(args.out / filename)
            else:
                filename = None
            pcm = np.frombuffer(chunk, '<i2').astype(np.int32)
            rows.append({'frame': frame, 'phase': phase, 'edge': edge,
                         'ident_error': ram[0x1FF4], 'ident_note': ram[0x1FF3],
                         'nmi': int.from_bytes(ram[0x1C04:0x1C06], 'little'),
                         'fault': ram[0x1C06], 'spc_timeout': ram[0x1C0B],
                         'video_sha256': hashlib.sha256(latest.tobytes()).hexdigest(),
                         'game_ram_sha256': hashlib.sha256(ram[:0x800]).hexdigest(),
                         'nonstack_game_ram_sha256': hashlib.sha256(ram[:0x100] + ram[0x200:0x800]).hexdigest(),
                         'vram_zero': len(vram) == 65536 and not any(vram),
                         'audio_peak': int(np.max(np.abs(pcm))) if len(pcm) else 0,
                         'audio_sample_count': len(pcm) // 2,
                         'image': filename})
            audio.extend(chunk)
    finally:
        core.retro_unload_game()
        core.retro_deinit()
    with wave.open(str(args.out / 'audio.wav'), 'wb') as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(round(av.timing.sample_rate))
        wav.writeframes(audio)
    report = {'rom_sha256': hashlib.sha256(payload).hexdigest(),
              'core_sha256': hashlib.sha256(args.core.read_bytes()).hexdigest(),
              'frames': rows, 'fps': av.timing.fps,
              'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (args.out / 'capture.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'frames': len(rows), 'out': str(args.out)}))


if __name__ == '__main__':
    main()
