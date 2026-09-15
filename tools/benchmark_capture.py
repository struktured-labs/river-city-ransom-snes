"""Phase-driven NES/SNES capture. Run each core in a fresh process.

This records evidence, not a correctness verdict. No saves, game RAM writes,
frame skipping or emulator speed overrides are used.
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import shutil
import wave

import numpy as np
from PIL import Image

try:
    from .smoke_libretro import Game, Variable, AVInfo
except ImportError:
    from smoke_libretro import Game, Variable, AVInfo

ROOT = Path(__file__).resolve().parents[1]
BUTTONS = {"B": 0, "Y": 1, "Select": 2, "Start": 3,
           "Up": 4, "Down": 5, "Left": 6, "Right": 7, "A": 8}
# Logical NES controls use each core's serial-controller mapping.
MAPPING = {"nes": {"A": 8, "B": 0}, "snes": {"A": 0, "B": 1}}
RECTS = {"menu": (88, 48, 184, 84), "settings": (64, 40, 192, 62),
         "story": (8, 168, 80, 188), "street": (8, 8, 56, 24)}
SCENARIO = [
    {"name": "boot_to_menu", "until": "menu", "frames": 2400},
    {"name": "menu", "frames": 60},
    {"name": "open_settings", "frames": 12, "buttons": ["Start"]},
    {"name": "wait_settings", "until": "settings", "frames": 2400},
    {"name": "settings", "frames": 60},
    {"name": "start_game", "frames": 12, "buttons": ["Start"]},
    {"name": "wait_story", "until": "story", "frames": 2400},
    {"name": "story", "frames": 60},
    {"name": "dismiss_story", "frames": 12, "buttons": ["A"]},
    {"name": "wait_street", "until": "street", "frames": 2400},
    {"name": "settle_street", "frames": 60},
    {"name": "idle", "frames": 180},
    {"name": "walk", "frames": 180, "buttons": ["Right"]},
    {"name": "attack", "frames": 180, "buttons": ["A"], "pulse": [20, 5]},
    {"name": "press_pause", "frames": 12, "buttons": ["Start"]},
    {"name": "pause_requested", "frames": 180},
    {"name": "press_resume", "frames": 12, "buttons": ["Start"]},
    {"name": "resume_requested", "frames": 180},
]


def scenario_for(name):
    if name == 'baseline':
        return SCENARIO
    if name == 'menu-audio':
        # No input transitions or encounters: isolate sustained menu audio.
        return [dict(SCENARIO[0]), {'name': 'menu_audio', 'frames': 1800}]
    if name in ('traversal', 'traversal-recovery'):
        # Begin the walk only after the actual street has been recognized.
        # Keep frequent immutable screenshots/RAM snapshots for scene-exit
        # auditing; do not infer progression from a wrapping scroll register.
        prefix = SCENARIO[:next(i for i, p in enumerate(SCENARIO) if p['name'] == 'walk')]
        phases = list(prefix) + [dict(name=f'right_{i:02d}', frames=120, buttons=['Right'])
                                 for i in range(36)]
        if name == 'traversal-recovery':
            phases += [dict(name=f'left_{i:02d}', frames=120, buttons=['Left']) for i in range(12)]
        return phases
    if name not in ('start', 'select', 'start-select', 'start-confirm'):
        raise ValueError('Unknown transition scenario')
    prefix = SCENARIO[:next(i for i,p in enumerate(SCENARIO) if p['name']=='walk')]
    buttons = {'start-select':['Start','Select'], 'start-confirm':['Start','A']}.get(name,[name.title()])
    phases = list(prefix)
    for index, button in enumerate(buttons):
        phases.extend([{'name':f'press_{index}_{button}', 'frames':12, 'buttons':[button]},
                       {'name':f'after_{index}_{button}', 'frames':300}])
    phases.extend([{'name':'exit_menu', 'frames':12, 'buttons':['B']},
                   {'name':'after_exit', 'frames':300}])
    return phases


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def decode_frame(raw, width, height, pitch, fmt):
    bpp = 4 if fmt == 1 else 2
    if fmt not in (0, 1, 2) or pitch < width * bpp or len(raw) != pitch * height:
        raise ValueError("Invalid video buffer")
    lines = np.frombuffer(raw, np.uint8).reshape(height, pitch)[:, :width*bpp].copy()
    words = lines.view('<u4' if bpp == 4 else '<u2').reshape(height, width).astype(np.uint32)
    if fmt == 1:
        channels = ((words >> 16) & 255, (words >> 8) & 255, words & 255)
    elif fmt == 2:
        channels = (((words >> 11) & 31)*255//31, ((words >> 5) & 63)*255//63, (words & 31)*255//31)
    else:
        channels = (((words >> 10) & 31)*255//31, ((words >> 5) & 31)*255//31, (words & 31)*255//31)
    return np.stack(channels, axis=-1).astype(np.uint8)


def signature(rgb, rect):
    x0, y0, x1, y1 = rect
    if rgb.shape[0] < y1 or rgb.shape[1] < x1:
        raise ValueError("Frame too small for phase classifier")
    # White glyph shape, not palette approximation or character/enemy placement.
    return np.min(rgb[y0:y1, x0:x1], axis=2) >= 192


def matches(rgb, reference, rect):
    wanted = signature(reference, rect)
    if np.count_nonzero(wanted) < 8:
        raise ValueError("Empty phase template would accept a blank screen")
    return np.array_equal(signature(rgb, rect), wanted)


def audio_stats(raw):
    pcm = np.frombuffer(raw, '<i2').astype(np.float64)
    if not len(pcm):
        return {"samples": 0, "rms": 0.0, "ac_rms": 0.0, "peak": 0}
    stereo = pcm.reshape(-1, 2)
    ac = stereo - np.mean(stereo, axis=0)
    return {"samples": len(pcm)//2, "rms": float(np.sqrt(np.mean(pcm*pcm))),
            "ac_rms": float(np.sqrt(np.mean(ac*ac))),
            "peak": int(np.max(np.abs(pcm)))}


def capture(core_path, rom_path, system, references, out, scenario_name='baseline'):
    scenario = scenario_for(scenario_name)
    out.mkdir(parents=True, exist_ok=False)
    # Bind classifiers to previously authenticated original-ROM captures.
    templates, template_hashes = {}, {}
    for name, (directory, frame) in references.items():
        manifest = json.loads((directory / "manifest.json").read_text())
        source = directory / f"frame-{frame:05d}.png"
        if sha(source) != manifest["files"][source.name]:
            raise ValueError("Reference capture identity mismatch")
        templates[name] = np.array(Image.open(source).convert("RGB"))
        shutil.copyfile(source, out / f"reference-{name}.png")
        template_hashes[name] = {"image": sha(source), "manifest": sha(directory / "manifest.json"),
                                 "source_rom": manifest["rom_sha256"], "rect": RECTS[name]}
    if len({value["source_rom"] for value in template_hashes.values()}) != 1:
        raise ValueError("Mixed reference ROMs")
    palette = Path('/usr/share/fceux/palettes/FCEUX.pal')
    palette_hash = sha(palette)
    if any(json.loads((directory / 'manifest.json').read_text())["palette_sha256"] != palette_hash
           for directory, frame in references.values()):
        raise ValueError("Reference palette mismatch")
    shutil.copyfile(palette, out / 'nes.pal')
    if system == "nes" and sha(rom_path) != template_hashes["menu"]["source_rom"]:
        raise ValueError("NES benchmark ROM differs from references")
    candidate_manifest = None
    if system == "snes":
        manifest_path = rom_path.parent / "manifest.json"
        candidate = json.loads(manifest_path.read_text())
        if candidate["rom_sha256"] != sha(rom_path) or candidate["source_rom_sha256"] != template_hashes["menu"]["source_rom"]:
            raise ValueError("SNES candidate/source manifest mismatch")
        candidate_manifest = sha(manifest_path)
    options = {b"snes9x_overscan": b"disabled", b"fceumm_overscan_h": b"disabled",
               b"fceumm_overscan_v": b"disabled", b"fceumm_palette": b"custom"}
    directory_bytes = str(out.resolve()).encode()
    core = C.CDLL(str(core_path.resolve()))
    getter = None
    if system == 'snes':
        try:
            getter = core.retro_rcr_cpu_register
        except AttributeError as error:
            raise RuntimeError('SNES capture requires the pinned debug-export core') from error
        getter.argtypes = [C.c_uint]
        getter.restype = C.c_uint
    fmt, latest, calls, duplicated = 0, None, 0, False
    frame_audio = bytearray()
    callback_errors = []
    held = set()
    delivered = set()

    @C.CFUNCTYPE(C.c_bool, C.c_uint, C.c_void_p)
    def environment(cmd, data):
        nonlocal fmt
        if cmd in (9, 31):
            C.cast(data, C.POINTER(C.c_char_p))[0] = directory_bytes
            return True
        if cmd == 10:
            fmt = C.cast(data, C.POINTER(C.c_int))[0]
            return fmt in (0, 1, 2)
        if cmd == 15:
            var = C.cast(data, C.POINTER(Variable)).contents
            if var.key in options:
                var.value = options[var.key]
                return True
        if cmd in (3, 17):
            C.cast(data, C.POINTER(C.c_bool))[0] = cmd == 3
            return True
        return False

    @C.CFUNCTYPE(None, C.c_void_p, C.c_uint, C.c_uint, C.c_size_t)
    def video(data, width, height, pitch):
        nonlocal latest, calls, duplicated
        calls += 1
        duplicated = not bool(data)
        try:
            if data:
                latest = decode_frame(C.string_at(data, pitch*height), width, height, pitch, fmt)
        except Exception as error:
            callback_errors.append(str(error))

    @C.CFUNCTYPE(None, C.c_int16, C.c_int16)
    def audio(left, right):
        frame_audio.extend(np.array([left, right], dtype='<i2').tobytes())

    @C.CFUNCTYPE(C.c_size_t, C.POINTER(C.c_int16), C.c_size_t)
    def batch(data, count):
        frame_audio.extend(np.ctypeslib.as_array(data, shape=(count*2,)).astype('<i2').tobytes())
        return count

    @C.CFUNCTYPE(None)
    def poll():
        pass

    @C.CFUNCTYPE(C.c_int16, C.c_uint, C.c_uint, C.c_uint, C.c_uint)
    def input_state(port, device, index, ident):
        value = int(port == 0 and device == 1 and index == 0 and ident in held)
        if value:
            delivered.add(ident)
        return value

    for name, callback in (("environment", environment), ("video_refresh", video),
                           ("audio_sample", audio), ("audio_sample_batch", batch),
                           ("input_poll", poll), ("input_state", input_state)):
        setter = getattr(core, "retro_set_" + name)
        setter.argtypes = [type(callback)]
        setter(callback)
    core.retro_get_memory_data.argtypes = [C.c_uint]
    core.retro_get_memory_data.restype = C.c_void_p
    core.retro_get_memory_size.argtypes = [C.c_uint]
    core.retro_get_memory_size.restype = C.c_size_t
    core.retro_load_game.argtypes = [C.POINTER(Game)]
    core.retro_load_game.restype = C.c_bool
    core.retro_get_system_av_info.argtypes = [C.POINTER(AVInfo)]
    core.retro_init()
    loaded = False
    payload = rom_path.read_bytes()
    data = C.create_string_buffer(payload)
    rows, segments, pcm, snapshots = [], [], bytearray(), {}
    try:
        game = Game(str(rom_path.resolve()).encode(), C.cast(data, C.c_void_p), len(payload), None)
        loaded = core.retro_load_game(C.byref(game))
        if not loaded:
            raise RuntimeError("Core refused ROM")
        av = AVInfo()
        core.retro_get_system_av_info(C.byref(av))
        if not 49 < av.timing.fps < 62 or not 8000 < av.timing.sample_rate < 192001:
            raise RuntimeError("Unexpected core timing")
        for phase in scenario:
            start, matched, stable = len(rows), False, 0
            for offset in range(phase["frames"]):
                buttons = phase.get("buttons", [])
                if "pulse" in phase and offset % phase["pulse"][0] >= phase["pulse"][1]:
                    buttons = []
                held = {MAPPING[system].get(button, BUTTONS[button]) for button in buttons}
                delivered.clear()
                frame_audio.clear()
                calls = 0
                core.retro_run()
                if callback_errors or calls != 1 or latest is None:
                    raise RuntimeError(f"Invalid callbacks: {calls}, {callback_errors}")
                size, ptr = core.retro_get_memory_size(2), core.retro_get_memory_data(2)
                if not ptr or size < 2048:
                    raise RuntimeError("Missing game RAM telemetry")
                ram = C.string_at(ptr, min(size, 8192))
                fault = None
                if system == "snes" and len(rows) >= 120:
                    if ram[0x1C06] or ram[0x1C0B] or ram[0x1C0A] > 1:
                        fault = "adapter_fault"
                    if ram[0x1C79] == 1 and ram[0x1C7B]:
                        fault = "vblank_overrun"
                rows.append({"frame": len(rows)+1, "phase": phase["name"],
                             "input_requested": sorted(held), "input_delivered": sorted(delivered),
                             "video_sha256": hashlib.sha256(latest.tobytes()).hexdigest(),
                             "video_duplicate_callback": duplicated, "audio": audio_stats(frame_audio),
                             "audio_start_sample": len(pcm)//4, "ram_sha256": hashlib.sha256(ram[:2048]).hexdigest(),
                             "probe_052b": ram[0x52B],
                             "nmi_counter": int.from_bytes(ram[0x1C04:0x1C06], "little") if system == "snes" else None,
                             "fault": fault})
                if scenario_name.startswith('traversal'):
                    # Preserve raw original-game state for deriving/validating
                    # position and room oracles, rather than naming guesses.
                    rows[-1]['game_ram_hex'] = ram[:2048].hex()
                if system == 'snes':
                    rows[-1]['native'] = {'pc':getter(0), 'p':getter(5), 'db':getter(6),
                        'task':ram[0x100], 'guard':ram[0x107], 'nmi_depth':ram[0x1C0A],
                        'ppu_ctrl':ram[0x1C20], 'ppu_mask':ram[0x1C21],
                        'gameplay_sound_services':ram[0x1C84],
                        'row_states': [ram[0x1D00:0x1D80].count(state) for state in range(4)],
                        'row_flags_hex': ram[0x1D00:0x1D80].hex(),
                        'producer_row': ram[0x1C76], 'consumer_row': ram[0x1C74],
                        'last_publish_entry_line': int.from_bytes(ram[0x1C7C:0x1C7E], 'little'),
                        'last_publish_exit_line': int.from_bytes(ram[0x1C7E:0x1C80], 'little'),
                        'chr_jobs_pending': sum(bool(value) for value in ram[0x1D80:0x1D98]),
                        'game_nmi_ticks_010b': ram[0x10B],
                        'scroll_x':ram[0x1C28], 'scroll_y':ram[0x1C29],
                        'publish_count':ram[0x1C7A], 'apu_packet':ram[0xA00:0xA17].hex()}
                pcm.extend(frame_audio)
                if "until" in phase:
                    hit = matches(latest, templates[phase["until"]], RECTS[phase["until"]])
                    stable = stable+1 if hit else 0
                    if stable >= 3:
                        matched = True
                        break
            name = phase["name"]
            Image.fromarray(latest).save(out / f"{name}.png")
            size, ptr = core.retro_get_memory_size(2), core.retro_get_memory_data(2)
            (out / f'{name}.ram').write_bytes(C.string_at(ptr, size))
            snapshots[name] = sha(out / f"{name}.png")
            segments.append({"name": name, "start_frame": start+1, "end_frame": len(rows),
                             "frames": len(rows)-start, "transition_matched": matched if "until" in phase else None,
                             "screenshot": f"{name}.png", "screenshot_sha256": snapshots[name],
                             "ram_snapshot": f"{name}.ram", "ram_snapshot_sha256": sha(out / f'{name}.ram')})
            if scenario_name.startswith('traversal') and system == 'snes':
                vram_size, vram_ptr = core.retro_get_memory_size(3), core.retro_get_memory_data(3)
                if not vram_ptr or vram_size != 65536:
                    raise RuntimeError('Missing SNES video RAM evidence')
                (out/f'{name}.vram').write_bytes(C.string_at(vram_ptr, vram_size))
                segments[-1].update(vram_snapshot=f'{name}.vram',
                                    vram_snapshot_sha256=sha(out/f'{name}.vram'))
            if "until" in phase and not matched:
                break  # fail closed: never label an unreached screen as gameplay/audio proof.
        with wave.open(str(out / "audio.wav"), "wb") as output:
            output.setnchannels(2)
            output.setsampwidth(2)
            output.setframerate(round(av.timing.sample_rate))
            output.writeframes(pcm)
        (out / "timeline.json").write_text(json.dumps(rows, separators=(",", ":")) + "\n")
        report = {"schema": "rcr-benchmark-capture-v1", "system": system,
                  "rom_sha256": sha(rom_path), "core_sha256": sha(core_path),
                  "candidate_manifest_sha256": candidate_manifest,
                  "palette_sha256": palette_hash,
                  "capture_tool_sha256": sha(Path(__file__)), "templates": template_hashes,
                  "scenario_name":scenario_name,
                  "scenario": scenario, "scenario_sha256": hashlib.sha256(json.dumps(scenario, sort_keys=True).encode()).hexdigest(),
                  "input_mapping": MAPPING[system], "core_options": {k.decode(): v.decode() for k,v in options.items()},
                  "fps": av.timing.fps, "sample_rate": av.timing.sample_rate,
                  "segments": segments, "audio_sha256": sha(out / "audio.wav"),
                  "timeline_sha256": sha(out / "timeline.json"), "frames": len(rows),
                  "capture_complete": len(segments) == len(scenario) and all(s["transition_matched"] is not False for s in segments),
                  "release_ready": False}
        (out / "capture.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({"out": str(out), "frames": len(rows), "complete": report["capture_complete"]}))
    finally:
        if loaded:
            core.retro_unload_game()
        core.retro_deinit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("core", "rom", "title", "walk", "out"):
        parser.add_argument("--"+name, type=Path, required=True)
    parser.add_argument("--system", choices=("nes", "snes"), required=True)
    parser.add_argument('--scenario',choices=('baseline','menu-audio','start','select','start-select','start-confirm','traversal','traversal-recovery'),default='baseline')
    args = parser.parse_args()
    refs = {"menu": (args.title, 600), "settings": (args.walk, 600),
            "story": (args.walk, 900), "street": (args.walk, 1800)}
    capture(args.core, args.rom, args.system, refs, args.out, args.scenario)
