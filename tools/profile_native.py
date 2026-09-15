"""Observe frame pacing using stock libretro callbacks and adapter WRAM counters."""
import argparse
import collections
import ctypes as C
import hashlib
import json
from pathlib import Path
import time

try:
    from . import smoke_libretro as smoke
except ImportError:
    import smoke_libretro as smoke


def profile(core_path, rom_path, frames=3600, warmup=1800):
    if not 0 < warmup < frames:
        raise ValueError("Need both warmup and measurement frames")
    real_cdll = C.CDLL
    rows, images, retained = [], [], []
    def loader(path):
        core = real_cdll(path)
        original_run, original_video = core.retro_run, core.retro_set_video_refresh
        def set_video(callback):
            @type(callback)
            def hooked(data, width, height, pitch):
                if data:
                    raw = C.string_at(data, height * pitch)
                    images.append((hashlib.sha256(raw).hexdigest(), not any(raw)))
                else:
                    images.append(images[-1] if images else (None, False))
                callback(data, width, height, pitch)
            retained.append(hooked)
            original_video.argtypes = [type(callback)]
            original_video(hooked)
        def step():
            begin = time.perf_counter()
            original_run()
            elapsed = time.perf_counter() - begin
            ram = C.string_at(core.retro_get_memory_data(2), 8192)
            rows.append({"frame": len(rows) + 1, "nmi": int.from_bytes(ram[0x1C04:0x1C06], "little"),
                         "camera_x": int.from_bytes(ram[0xDC:0xDE], 'little'),
                         "street_scroll_x": ram[0xF6] | ((ram[0x3D] & 1) << 8),
                         "hdma_street_scroll_x": ram[0x1C94] | ((ram[0x1C95] & 1) << 8),
                         "game_tick": ram[0x52B], "guard_ready": ram[0x1C79] == 1,
                         "vblank_overrun": ram[0x1C79] == 1 and ram[0x1C7B] == 1,
                         "host_seconds": elapsed})
        core.retro_run, core.retro_set_video_refresh = step, set_video
        return core
    smoke.C.CDLL = loader
    try:
        receipt = smoke.run(core_path, rom_path, frames, kind="native", profile="walk")
    finally:
        smoke.C.CDLL = real_cdll
    if len(images) != frames:
        raise RuntimeError("Expected exactly one video callback per emulated frame")
    events = []
    for previous, current in zip(rows[warmup-1:-1], rows[warmup:]):
        delta = current["nmi"] - previous["nmi"]
        if not 0 <= delta < 10:
            raise RuntimeError("NMI reset or impossible nesting during profile")
        events.extend([current["frame"]] * delta)
    intervals = [b-a for a,b in zip(events, events[1:])]
    seconds = (frames - warmup) / 60.1
    changed = sum(images[i][0] != images[i-1][0] for i in range(warmup, frames))
    ticks = sum(a["game_tick"] != b["game_tick"] for a,b in zip(rows[warmup-1:-1], rows[warmup:]))
    return {"schema": "rcr-frame-pacing-v1", "receipt": receipt,
            "profile_tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "measurement_frames": [warmup + 1, frames], "input_profile": "walk",
            "camera_x_range": [min(r['camera_x'] for r in rows[warmup:]), max(r['camera_x'] for r in rows[warmup:])],
            "street_scroll_x_range": [min(r['street_scroll_x'] for r in rows[warmup:]), max(r['street_scroll_x'] for r in rows[warmup:])],
            "hdma_street_scroll_x_range": [min(r['hdma_street_scroll_x'] for r in rows[warmup:]), max(r['hdma_street_scroll_x'] for r in rows[warmup:])],
            "nmi_per_second": len(events)/seconds,
            "nmi_gap_display_frames": dict(sorted(collections.Counter(intervals).items())),
            "max_nmi_gap_display_frames": max(intervals, default=0),
            "picture_changes_per_second": changed/seconds,
            "game_tick_changes_per_second": ticks/seconds,
            "black_display_frames": sum(image[1] for image in images[warmup:]),
            "vblank_overrun_seen": any(row["vblank_overrun"] for row in rows) if any(row["guard_ready"] for row in rows) else None,
            "host_emulation_seconds": sum(row["host_seconds"] for row in rows[warmup:])}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--frames", type=int, default=3600)
    parser.add_argument("--warmup", type=int, default=1800)
    args = parser.parse_args()
    result = profile(args.core, args.rom, args.frames, args.warmup)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
