"""Run the diagnostic with a Snes9x libretro core; assert live CPU and sound."""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import struct
import wave


class Game(C.Structure):
    _fields_ = [("path", C.c_char_p), ("data", C.c_void_p),
                ("size", C.c_size_t), ("meta", C.c_char_p)]


class Variable(C.Structure):
    _fields_ = [("key", C.c_char_p), ("value", C.c_char_p)]


class Geometry(C.Structure):
    _fields_ = [("base_width", C.c_uint), ("base_height", C.c_uint),
                ("max_width", C.c_uint), ("max_height", C.c_uint),
                ("aspect_ratio", C.c_float)]


class Timing(C.Structure):
    _fields_ = [("fps", C.c_double), ("sample_rate", C.c_double)]


class AVInfo(C.Structure):
    _fields_ = [("geometry", Geometry), ("timing", Timing)]


def check_native(ram, previous=None):
    """Fail on adapter faults/reset, not just missing emulator callbacks."""
    if len(ram) < 0x1C47:
        raise RuntimeError("Missing native runtime WRAM")
    counter = int.from_bytes(ram[0x1C04:0x1C06], "little")
    if ram[0x1C06] or ram[0x1C0B]:
        raise RuntimeError("Native adapter reported unknown I/O or SPC timeout")
    if ram[0x1C0A] > 1:
        raise RuntimeError("Native NMI nesting/stack invariant failed")
    if previous is not None and counter <= previous:
        raise RuntimeError("Native NMI counter stalled or reset")
    return counter


def run(core_path, rom_path, frames, wav_path=None, kind="audio", screenshot=None, ram_path=None, profile="title"):
    core = C.CDLL(str(core_path.resolve()))
    samples = bytearray()
    video_frames = 0
    pixel_format = 0
    last_image = None
    system_dir = str(rom_path.resolve().parent).encode()

    @C.CFUNCTYPE(C.c_bool, C.c_uint, C.c_void_p)
    def environment(cmd, data):
        nonlocal pixel_format
        if cmd in (9, 31):  # GET_SYSTEM_DIRECTORY / GET_SAVE_DIRECTORY
            C.cast(data, C.POINTER(C.c_char_p))[0] = system_dir
            return True
        if cmd == 10:  # SET_PIXEL_FORMAT (0RGB1555, XRGB8888, RGB565)
            pixel_format = C.cast(data, C.POINTER(C.c_int))[0]
            return pixel_format in (0, 1, 2)
        if cmd == 15:  # GET_VARIABLE: use core defaults
            var = C.cast(data, C.POINTER(Variable)).contents
            if var.key == b"snes9x_overscan":
                var.value = b"disabled"
                return True
            return False
        if cmd == 17:  # GET_VARIABLE_UPDATE
            C.cast(data, C.POINTER(C.c_bool))[0] = False
            return True
        if cmd == 3:  # GET_CAN_DUPE
            C.cast(data, C.POINTER(C.c_bool))[0] = True
            return True
        return False

    @C.CFUNCTYPE(None, C.c_void_p, C.c_uint, C.c_uint, C.c_size_t)
    def video(data, width, height, pitch):
        nonlocal video_frames, last_image
        if data and width and height:
            video_frames += 1
            if screenshot:
                last_image = (width, height, pitch, pixel_format, C.string_at(data, pitch * height))

    @C.CFUNCTYPE(None, C.c_int16, C.c_int16)
    def audio(left, right):
        samples.extend(struct.pack("<hh", left, right))

    @C.CFUNCTYPE(C.c_size_t, C.POINTER(C.c_int16), C.c_size_t)
    def batch(data, count):
        # libretro samples are native-endian int16; WAV requires little-endian.
        samples.extend(struct.pack(f"<{count * 2}h", *data[:count * 2]))
        return count

    @C.CFUNCTYPE(None)
    def poll():
        pass

    @C.CFUNCTYPE(C.c_int16, C.c_uint, C.c_uint, C.c_uint, C.c_uint)
    def input_state(port, device, index, ident):
        if port == 0 and device == 1 and profile == "walk":
            n = frame + 1
            return int((ident == 3 and any(start <= n < start + 30 for start in (600, 1000, 1400))) or
                       (ident == 7 and n >= 1600) or
                       (ident == 0 and n >= 1800 and n % 20 < 5))
        return 0

    for name, callback in (("environment", environment), ("video_refresh", video),
                           ("audio_sample", audio), ("audio_sample_batch", batch),
                           ("input_poll", poll), ("input_state", input_state)):
        fn = getattr(core, "retro_set_" + name)
        fn.argtypes = [type(callback)]
        fn.restype = None
        fn(callback)
    core.retro_load_game.argtypes = [C.POINTER(Game)]
    core.retro_load_game.restype = C.c_bool
    core.retro_get_memory_data.argtypes = [C.c_uint]
    core.retro_get_memory_data.restype = C.c_void_p
    core.retro_get_memory_size.argtypes = [C.c_uint]
    core.retro_get_memory_size.restype = C.c_size_t
    core.retro_get_system_av_info.argtypes = [C.POINTER(AVInfo)]
    core.retro_init()
    loaded = False
    try:
        payload = rom_path.read_bytes()
        data = C.create_string_buffer(payload)
        game = Game(str(rom_path.resolve()).encode(), C.cast(data, C.c_void_p), len(payload), None)
        if not core.retro_load_game(C.byref(game)):
            raise RuntimeError("Core refused diagnostic ROM")
        loaded = True
        av = AVInfo()
        core.retro_get_system_av_info(C.byref(av))
        frame_counts = []
        for frame in range(frames):
            core.retro_run()
            if kind == "native" and (frame + 1) % 300 == 0:
                ptr = core.retro_get_memory_data(2)
                size = core.retro_get_memory_size(2)
                if not ptr or size != 131072:
                    raise RuntimeError("Expected 128 KiB native WRAM")
                ram = C.string_at(ptr, size)
                frame_counts.append(check_native(ram, frame_counts[-1] if frame_counts else None))
            if kind == "audio" and frame in (frames // 2, frames - 1):
                ptr = core.retro_get_memory_data(2)  # RETRO_MEMORY_SYSTEM_RAM
                size = core.retro_get_memory_size(2)
                if not ptr or size < 0xA23:
                    raise RuntimeError("Core did not expose SNES WRAM")
                ram = C.string_at(ptr, size)
                if ram[0xA22] != 1:
                    raise RuntimeError(f"Diagnostic failed: WRAM status={ram[0xA22]:02x}")
                frame_counts.append(int.from_bytes(ram[0xA20:0xA22], "little"))
        # Exclude IPL/startup transients: inspect only the second half of audio.
        values = struct.unpack(f"<{len(samples) // 2}h", samples)
        steady = values[len(values) // 2:]
        peak = max(map(abs, steady), default=0)
        if video_frames < frames // 2 or (kind == "audio" and frame_counts[1] <= frame_counts[0]):
            raise RuntimeError("CPU/video stopped advancing")
        if kind == "audio" and (peak < 128 or len(set(steady)) < 16):
            raise RuntimeError("No sustained audio waveform")
        if wav_path:
            with wave.open(str(wav_path), "wb") as output:
                output.setnchannels(2)
                output.setsampwidth(2)
                output.setframerate(round(av.timing.sample_rate))
                output.writeframes(samples)
        if screenshot:
            if last_image is None:
                raise RuntimeError("No rendered image captured")
            from PIL import Image
            width, height, pitch, fmt, raw = last_image
            pixels = bytearray()
            for y in range(height):
                for x in range(width):
                    offset = y * pitch + x * (4 if fmt == 1 else 2)
                    value = int.from_bytes(raw[offset:offset + (4 if fmt == 1 else 2)], "little")
                    if fmt == 1:
                        rgb = ((value >> 16) & 255, (value >> 8) & 255, value & 255)
                    elif fmt == 2:
                        rgb = (((value >> 11) & 31) * 255 // 31, ((value >> 5) & 63) * 255 // 63, (value & 31) * 255 // 31)
                    else:
                        rgb = (((value >> 10) & 31) * 255 // 31, ((value >> 5) & 31) * 255 // 31, (value & 31) * 255 // 31)
                    pixels.extend(rgb)
            Image.frombytes("RGB", (width, height), bytes(pixels)).save(screenshot)
        if ram_path:
            size = core.retro_get_memory_size(2)
            ptr = core.retro_get_memory_data(2)
            if not ptr or size != 131072:
                raise RuntimeError("Expected 128 KiB SNES WRAM")
            ram_path.write_bytes(C.string_at(ptr, size))
        registers = {}
        if hasattr(core, "retro_rcr_cpu_register"):
            getter = core.retro_rcr_cpu_register
            getter.argtypes = [C.c_uint]
            getter.restype = C.c_uint
            registers = {key: f"{getter(i):06x}" for i, key in enumerate(("pc", "a", "x", "y", "s", "p", "db", "d"))}
        return {"schema": "rcr-emulator-receipt-v1", "emulated_frames": frames, "video_frames": video_frames, "input_profile": profile,
                "rom_sha256": hashlib.sha256(payload).hexdigest(),
                "core_sha256": hashlib.sha256(core_path.read_bytes()).hexdigest(),
                "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "audio_pcm_sha256": hashlib.sha256(samples).hexdigest(),
                "screenshot_sha256": hashlib.sha256(screenshot.read_bytes()).hexdigest() if screenshot else None,
                "game_frame_counters": frame_counts, "audio_peak": peak,
                "sample_rate": av.timing.sample_rate, "status": "passed",
                "scope": {"audio": "CPU/audio diagnostic", "render": "video callbacks only; not game correctness",
                          "native": "NMI progress and adapter fault checks; NOT gameplay/audio/visual fidelity"}[kind],
                "cpu": registers}
    finally:
        if loaded:
            core.retro_unload_game()
        core.retro_deinit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--rom", type=Path, default=Path("build/audio-bringup.sfc"))
    parser.add_argument("--frames", type=int, default=300)
    parser.add_argument("--wav", type=Path)
    parser.add_argument("--kind", choices=("audio", "render", "native"), default="audio")
    parser.add_argument("--screenshot", type=Path)
    parser.add_argument("--ram", type=Path)
    parser.add_argument("--profile", choices=("title", "walk"), default="title")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    if args.frames < 120 or args.frames > 30000:
        parser.error("Use 120..30000 frames to allow SPC startup and avoid counter wrap")
    if args.kind == "native" and args.frames < 600:
        parser.error("Native checks require at least 600 frames")
    result = run(args.core, args.rom, args.frames, args.wav, args.kind, args.screenshot, args.ram, args.profile)
    if args.receipt:
        args.receipt.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
