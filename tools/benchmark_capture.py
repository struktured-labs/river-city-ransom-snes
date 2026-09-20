"""Phase-driven NES/SNES capture. Run each core in a fresh process.

This records evidence, not a correctness verdict. No saves, game RAM writes,
frame skipping or emulator speed overrides are used.
"""
import argparse
import ctypes as C
import hashlib
import json
import os
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
           "Up": 4, "Down": 5, "Left": 6, "Right": 7, "A": 8,
           "X": 9, "L": 10, "R": 11,
           "PadB": 0, "PadY": 1, "PadA": 8, "PadX": 9}
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


def waypoint_policy(name):
    # Keep historical café policy hashes and scenarios valid.
    import importlib
    if name == 'traversal-expanded-sweep':
        return importlib.import_module((__package__+'.' if __package__ else '')+'coverage_waypoints')
    module='park_waypoints' if name in ('traversal-park-coverage','traversal-park-single-sweep') else 'traversal_waypoints'
    return importlib.import_module((__package__+'.' if __package__ else '')+module)


def validate_render_options(environment):
    allowed = {'RCR_RENDER_SCROLL_TRACE', 'RCR_RENDER_FIRST', 'RCR_RENDER_LAST'}
    unknown = {key for key in environment if key.startswith('RCR_RENDER_')} - allowed
    if unknown:
        raise ValueError('Unknown renderer observer option: '+', '.join(sorted(unknown)))
    if environment.get('RCR_RENDER_SCROLL_TRACE'):
        first = int(environment.get('RCR_RENDER_FIRST', '7600'))
        last = int(environment.get('RCR_RENDER_LAST', '8420'))
        if not 1 <= first <= last:
            raise ValueError('Invalid renderer observation bounds')


def scenario_for(name):
    if name == 'combat-knockdown-audio':
        # Input-only encounter: let the original enemies reach the player.
        # Keep every frame, including death/recovery or a missed pause. Phase
        # names describe requests, not proof that a knockdown/pause occurred.
        prefix = SCENARIO[:next(i for i,p in enumerate(SCENARIO) if p['name']=='idle')]
        return list(prefix) + [
            dict(name='idle',frames=180),
            dict(name='combat_approach',frames=60,buttons=['Right']),
            dict(name='combat_take_hits',frames=720),
            dict(name='combat_counterattack',frames=240,buttons=['A'],pulse=[30,6]),
            dict(name='combat_pause_request',frames=12,buttons=['Start']),
            dict(name='combat_pause_wait',frames=180),
            dict(name='combat_resume_request',frames=12,buttons=['Start']),
            dict(name='combat_resume_wait',frames=180),
        ]
    if name == 'traversal-expanded-sweep':
        phases = list(scenario_for('traversal-jump'))
        for cycle in range(2):
            for direction in ('west', 'east'):
                phases += [dict(name=f'alley_{cycle:02d}_{direction}_sweep', frames=1920,
                                waypoint='alley-'+direction),
                           dict(name=f'alley_{cycle:02d}_{direction}_settle', frames=30)]
        shop = scenario_for('traversal-waypoint-shop')
        phases += shop[len(scenario_for('traversal-jump')):]
        park = scenario_for('traversal-park-single-sweep')
        return phases + park[next(i for i,p in enumerate(park) if p['name']=='leave_shop'):]
    if name=='traversal-park-single-sweep':
        # Separate dense scenery test. The four-cycle endurance route above
        # remains unchanged and can fail independently after this first lap.
        old=scenario_for('traversal-park-coverage')
        return old[:next(i for i,p in enumerate(old) if p['name']=='park_01_east_sweep')]
    if name=='traversal-park-coverage':
        old=scenario_for('traversal-shop-exit')
        phases=old[:next(i for i,p in enumerate(old) if p['name']=='mall_right_00')]
        phases += [dict(name='park_entry',frames=1920,waypoint='park-entry')]
        for cycle in range(4):
            for direction in ('east','west'):
                phases += [dict(name=f'park_{cycle:02d}_{direction}_sweep',frames=1920,
                                waypoint='park-'+direction),
                           dict(name=f'park_{cycle:02d}_{direction}_settle',frames=30)]
        return phases
    if name in ('traversal-waypoint-shop','traversal-waypoint-shop-repeat','traversal-waypoint-shop-no'):
        phases=scenario_for('traversal-jump')+[
            dict(name='reach_mall',frames=1920,waypoint='mall'),
            dict(name='observe_alley_exit',frames=120),
            dict(name='enter_cafe',frames=1200,waypoint='cafe'),
            dict(name='observe_shop',frames=180)]
        if name!='traversal-waypoint-shop':
            suffix=name.removeprefix('traversal-waypoint-')
            phases+=scenario_for('traversal-'+suffix)[len(scenario_for('traversal-shop')):]
        return phases
    if name == 'baseline':
        return SCENARIO
    if name == 'traversal-park-stress':
        # Ordinary input-only route reaches the U.S. Mail park (room 3).
        # Alternate double-tap runs without moving up into a shop. A later
        # audit must prove room coverage; completion alone cannot certify it.
        phases = scenario_for('traversal-shop-exit') + [
            dict(name='park_arrival', frames=60),
        ]
        for cycle in range(8):
            for direction in ('Right', 'Left'):
                label = f'park_{cycle:02d}_{direction.lower()}'
                phases += [
                    dict(name=label+'_tap', frames=2, buttons=[direction]),
                    dict(name=label+'_release', frames=4),
                    dict(name=label+'_run', frames=72, buttons=[direction]),
                    dict(name=label+'_settle', frames=6),
                ]
            if cycle in (2, 5):
                phases += [
                    dict(name=f'park_{cycle:02d}_pause', frames=12, buttons=['Start']),
                    dict(name=f'park_{cycle:02d}_paused', frames=120),
                    dict(name=f'park_{cycle:02d}_resume', frames=12, buttons=['Start']),
                    dict(name=f'park_{cycle:02d}_resumed', frames=90),
                ]
        return phases
    if name == 'controls-presets':
        # Independent shoulder rising edges; retain the default Classic on
        # return. All four screenshots are from the real game's settings.
        return list(SCENARIO[:5]) + [
            dict(name='controls_classic', frames=60),
            dict(name='controls_right_nintendo', frames=12, buttons=['R']),
            dict(name='controls_nintendo', frames=60),
            dict(name='controls_right_arcade', frames=12, buttons=['R']),
            dict(name='controls_arcade', frames=60),
            dict(name='controls_right_reverse', frames=12, buttons=['R']),
            dict(name='controls_reverse', frames=60),
            dict(name='controls_left_arcade', frames=12, buttons=['L']),
            dict(name='controls_arcade_again', frames=60),
            dict(name='controls_left_nintendo', frames=12, buttons=['L']),
            dict(name='controls_nintendo_again', frames=60),
            dict(name='controls_left_classic', frames=12, buttons=['L']),
            dict(name='controls_classic_again', frames=60),
        ]
    if name == 'pause-status-after-combat':
        phases=scenario_for('pause-status')+[
            dict(name='status_walk_to_goons',frames=90,buttons=['Right']),
            dict(name='status_encounter',frames=240),
            dict(name='status_pause_after_combat',frames=12,buttons=['Start']),
            dict(name='status_selector_after_combat',frames=120),
        ]
        for i in range(3):
            phases += [dict(name=f'status_combat_right_{i}',frames=12,buttons=['Right']),
                       dict(name=f'status_combat_right_idle_{i}',frames=60)]
        return phases + [dict(name='status_open_after_combat',frames=12,buttons=['A']),
                         dict(name='status_visible_after_combat',frames=180)]
    if name == 'pause-status':
        route = scenario_for('pause-cursor-return')
        prefix = route[:next(i for i,p in enumerate(route) if p['name']=='pause_right_4')]
        return prefix + [
            dict(name='status_open',frames=12,buttons=['A']),
            dict(name='status_visible',frames=180),
            dict(name='status_cancel',frames=12,buttons=['B']),
            dict(name='status_cancel_visible',frames=90),
            dict(name='status_reopen',frames=12,buttons=['A']),
            dict(name='status_reopen_visible',frames=180),
            dict(name='status_cancel_again',frames=12,buttons=['B']),
            dict(name='status_after_cancel',frames=90),
            dict(name='status_resume',frames=12,buttons=['Start']),
            dict(name='status_gameplay',frames=120),
        ]
    if name == 'pause-cursor-return':
        # Probe the five labels by moving the original single cursor right
        # several times; the user saw LEVEL with BELONGINGS still marked.
        prefix = SCENARIO[:next(i for i,p in enumerate(SCENARIO) if p['name'] == 'idle')]
        return list(prefix) + [
            dict(name='before_pause', frames=60),
            dict(name='pause_open', frames=12, buttons=['Start']),
            dict(name='pause_visible', frames=120),
            dict(name='pause_right_1', frames=12, buttons=['Right']),
            dict(name='pause_right_visible_1', frames=90),
            dict(name='pause_right_2', frames=12, buttons=['Right']),
            dict(name='pause_right_visible_2', frames=90),
            dict(name='pause_right_3', frames=12, buttons=['Right']),
            dict(name='pause_right_visible_3', frames=90),
            dict(name='pause_right_4', frames=12, buttons=['Right']),
            dict(name='pause_right_visible_4', frames=90),
            dict(name='pause_cancel', frames=12, buttons=['B']),
            dict(name='pause_cancel_visible', frames=90),
            dict(name='pause_close', frames=12, buttons=['Start']),
            dict(name='game_after_pause', frames=120),
            dict(name='pause_reopen', frames=12, buttons=['Start']),
            dict(name='pause_reopen_visible', frames=120),
        ]
    if name == 'movement-probe':
        prefix = SCENARIO[:next(i for i,p in enumerate(SCENARIO) if p['name'] == 'walk')]
        return list(prefix) + [
            dict(name='move_right', frames=24, buttons=['Right']),
            dict(name='right_stop', frames=8),
            dict(name='move_left', frames=24, buttons=['Left']),
            dict(name='left_stop', frames=8),
        ]
    if name == 'menu-audio':
        # No input transitions or encounters: isolate sustained menu audio.
        return [dict(SCENARIO[0]), {'name': 'menu_audio', 'frames': 1800}]
    if name == 'traversal-shop-exit':
        return scenario_for('traversal-shop') + [
            dict(name='leave_shop', frames=12, buttons=['B']),
            dict(name='observe_shop_exit', frames=180),
            dict(name='mall_lower_lane', frames=60, buttons=['Down']),
        ] + [dict(name=f'mall_right_{i:02d}', frames=120, buttons=['Right']) for i in range(8)]
    if name == 'traversal-shop-confirm':
        # Select an item, then stop pressing buttons: the yes/no prompt must
        # render without an extra keypress or gameplay-state shortcut.
        return scenario_for('traversal-shop') + [
            dict(name='shop_select_item', frames=12, buttons=['A']),
            dict(name='shop_confirm_idle_1', frames=30),
            dict(name='shop_confirm_idle_2', frames=60),
            dict(name='shop_confirm_idle_3', frames=120),
        ]
    if name == 'traversal-shop-repeat':
        # Accept the first YES, advance any post-purchase dialogue, then
        # revisit the item list without leaving the shop. Each input has an
        # independent long release so a held A cannot auto-confirm twice.
        return scenario_for('traversal-shop-confirm') + [
            dict(name='shop_accept_yes', frames=12, buttons=['A']),
            dict(name='shop_after_purchase_1', frames=180),
            dict(name='shop_continue_1', frames=12, buttons=['A']),
            dict(name='shop_after_purchase_2', frames=180),
            dict(name='shop_continue_2', frames=12, buttons=['A']),
            dict(name='shop_after_purchase_3', frames=180),
            dict(name='shop_continue_3', frames=12, buttons=['A']),
            dict(name='shop_after_purchase_4', frames=120),
            dict(name='shop_select_second', frames=12, buttons=['A']),
            dict(name='shop_second_confirm', frames=120),
            dict(name='shop_accept_second', frames=12, buttons=['A']),
            dict(name='shop_after_purchase_5', frames=120),
        ]
    if name == 'traversal-shop-no':
        # Menu NO is selected by the original horizontal D-pad, not Select.
        # Observe right, left, and right again before confirming NO.
        return scenario_for('traversal-shop-confirm') + [
            dict(name='shop_choose_no', frames=12, buttons=['Right']),
            dict(name='shop_no_idle', frames=90),
            dict(name='shop_choose_yes_again', frames=12, buttons=['Left']),
            dict(name='shop_yes_idle', frames=90),
            dict(name='shop_choose_no_again', frames=12, buttons=['Right']),
            dict(name='shop_no_again_idle', frames=90),
            dict(name='shop_confirm_no', frames=12, buttons=['A']),
            dict(name='shop_no_result', frames=180),
        ]
    if name == 'traversal-shop':
        return scenario_for('traversal-mall') + [
            dict(name='approach_shop', frames=88, buttons=['Right']),
            dict(name='enter_shop', frames=180, buttons=['Up']),
            dict(name='observe_shop', frames=180),
        ]
    if name == 'traversal-mall':
        # The next area is reached through the alley, not the right wall.
        # This is still an attempted route; scene arrival is audited separately.
        return scenario_for('traversal-jump') + [
            dict(name='align_alley', frames=60, buttons=['Left']),
            dict(name='enter_alley', frames=180, buttons=['Up']),
            dict(name='observe_alley_exit', frames=120),
        ]
    if name in ('traversal', 'traversal-recovery', 'traversal-upper', 'traversal-jump', 'traversal-jump-lower'):
        # Begin the walk only after the actual street has been recognized.
        # Keep frequent immutable screenshots/RAM snapshots for scene-exit
        # auditing; do not infer progression from a wrapping scroll register.
        prefix = SCENARIO[:next(i for i, p in enumerate(SCENARIO) if p['name'] == 'walk')]
        # An alternate lane is an input-only exploration, not a claim that
        # a particular room or shop has been reached.
        lane = [dict(name='move_upper_lane', frames=90, buttons=['Up'])] if name == 'traversal-upper' else []
        phases = list(prefix) + lane + [dict(name=f'right_{i:02d}', frames=120, buttons=['Right'])
                                 for i in range(36)]
        if name == 'traversal-recovery':
            phases += [dict(name=f'left_{i:02d}', frames=120, buttons=['Left']) for i in range(12)]
        if name.startswith('traversal-jump'):
            for phase in phases[len(prefix):]:
                phase.update(buttons=['Right', 'A', 'B'], pulse=[30, 4], hold_buttons=['Right'])
        if name == 'traversal-jump-lower':
            phases += [dict(name='move_lower_lane', frames=90, buttons=['Down'])]
            phases += [dict(name=f'lower_right_{i:02d}', frames=120, buttons=['Right', 'A', 'B'],
                            pulse=[30, 4], hold_buttons=['Right']) for i in range(18)]
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


def bind_spc_observations(environ):
    """Flush host-only SPC logs before binding them to this completed replay."""
    requested = {field: Path(environ[variable]) for field, variable in (
        ('game_keyon_trace', 'RCR_SPC_GAME_KEYON_TRACE'),
        ('spc_receive_trace', 'RCR_SPC_RECEIVE_TRACE'),
        ('spc_synth_trace', 'RCR_SPC_SYNTH_TRACE')) if environ.get(variable)}
    if not requested:
        return {}
    flush = C.CDLL(None).fflush
    flush.argtypes = [C.c_void_p]
    flush.restype = C.c_int
    if flush(None) != 0:
        raise ValueError('Cannot flush SPC observations')
    result = {}
    for field, path in requested.items():
        if not path.is_file() or not path.stat().st_size:
            raise ValueError('Missing or empty SPC observation: '+str(path))
        result[field] = dict(path=str(path.resolve()), sha256=sha(path))
    return result


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


def capture(core_path, rom_path, system, references, out, scenario_name='baseline', frame_images=False,
            full_ram_telemetry=False, ppu_telemetry=False, palette_telemetry=False, background_telemetry=False):
    validate_render_options(os.environ)
    if palette_telemetry and system!='snes':raise ValueError('Palette WRAM telemetry is SNES-only')
    if palette_telemetry:
        try:
            from .palette_telemetry import read as read_palette
        except ImportError:
            from palette_telemetry import read as read_palette
    if ppu_telemetry and system != 'nes':
        raise ValueError('PPU register-map telemetry is NES-only')
    if ppu_telemetry:
        try:
            from .libretro_memory import SET_MEMORY_MAPS, ppu_pointer, read_ppu
        except ImportError:
            from libretro_memory import SET_MEMORY_MAPS, ppu_pointer, read_ppu
    ppu_address = None
    scenario = scenario_for(scenario_name)
    has_waypoints=any('waypoint' in p for p in scenario)
    policy=waypoint_policy(scenario_name) if has_waypoints else None
    if has_waypoints:
        frame_images=True
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
    boot_policy = None
    if system == "snes":
        manifest_path = rom_path.parent / "manifest.json"
        candidate = json.loads(manifest_path.read_text())
        if candidate["rom_sha256"] != sha(rom_path) or candidate["source_rom_sha256"] != template_hashes["menu"]["source_rom"]:
            raise ValueError("SNES candidate/source manifest mismatch")
        candidate_manifest = sha(manifest_path)
        try:
            from .boot_faults import binding, Monitor, registers
        except ImportError:
            from boot_faults import binding, Monitor, registers
        boot_policy = binding(rom_path.read_bytes(), candidate)
        boot_monitor = Monitor() if boot_policy else None
        if boot_policy:
            shutil.copyfile(manifest_path, out / 'boot-manifest.json')
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
    mapper_getter = getattr(core, 'retro_rcr_mmc3_register', None) if system == 'nes' else None
    if mapper_getter is not None:
        mapper_getter.argtypes = [C.c_uint]
        mapper_getter.restype = C.c_uint
    fmt, latest, calls, duplicated = 0, None, 0, False
    frame_audio = bytearray()
    callback_errors = []
    held = set()
    delivered = set()

    @C.CFUNCTYPE(C.c_bool, C.c_uint, C.c_void_p)
    def environment(cmd, data):
        nonlocal fmt, ppu_address
        if ppu_telemetry and cmd == SET_MEMORY_MAPS:
            try:
                ppu_address = ppu_pointer(data)
                return True
            except Exception as error:
                callback_errors.append(str(error))
                return False
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
    background=None
    if background_telemetry:
        try:
            from .background_observer import Observer, sources as background_sources
        except ImportError:
            from background_observer import Observer, sources as background_sources
        background=Observer(core)
        background_hashes={str(p.relative_to(ROOT)):sha(p) for p in background_sources(ROOT,system)}
        (out/'background').mkdir()
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
                if 'waypoint' in phase:
                    buttons=policy.buttons(phase['waypoint'],bytes.fromhex(rows[-1]['game_ram_hex']),offset,
                                     rows[-1]['waypoint_cursor'])
                if "pulse" in phase and offset % phase["pulse"][0] >= phase["pulse"][1]:
                    buttons = phase.get('hold_buttons', [])
                held = {MAPPING[system].get(button, BUTTONS[button]) for button in buttons}
                delivered.clear()
                frame_audio.clear()
                calls = 0
                if background:background.reset()
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
                if scenario_name in ('traversal-park-stress','traversal-park-coverage','traversal-park-single-sweep','traversal-expanded-sweep'):
                    rows[-1]['scene_sha256'] = hashlib.sha256(latest[32:192].tobytes()).hexdigest()
                if full_ram_telemetry or scenario_name.startswith('traversal') or scenario_name == 'movement-probe':
                    # Preserve raw original-game state for deriving/validating
                    # position and room oracles, rather than naming guesses.
                    rows[-1]['game_ram_hex'] = ram[:2048].hex()
                if mapper_getter is not None:
                    rows[-1]['nes_mapper'] = {'registers': [mapper_getter(i) for i in range(8)],
                                              'select': mapper_getter(8), 'mirror': mapper_getter(9)}
                if ppu_telemetry:
                    rows[-1]['nes_ppu'] = read_ppu(ppu_address)
                if palette_telemetry:
                    rows[-1]['snes_palette'] = read_palette(ptr,size)
                if system == 'snes':
                    rows[-1]['native'] = {'pc':getter(0), 'p':getter(5), 'db':getter(6),
                        'task':ram[0x100], 'guard':ram[0x107], 'nmi_depth':ram[0x1C0A],
                        'ppu_ctrl':ram[0x1C20], 'ppu_mask':ram[0x1C21],
                        'transition_state':ram[0x1CA0],
                        'transition_rows_hex':ram[0x1E80:0x1F00].hex(),
                        'mapper_select':ram[0x1C19], 'chr_registers':list(ram[0x1C10:0x1C16]),
                        'gameplay_sound_services':ram[0x1C84],
                        'row_states': [ram[0x1D00:0x1D80].count(state) for state in range(4)],
                        'row_flags_hex': ram[0x1D00:0x1D80].hex(),
                        'producer_row': ram[0x1C76], 'consumer_row': ram[0x1C74],
                        'last_publish_entry_line': int.from_bytes(ram[0x1C7C:0x1C7E], 'little'),
                        'last_publish_exit_line': int.from_bytes(ram[0x1C7E:0x1C80], 'little'),
                        'vblank_overrun_latch': ram[0x1C7B],
                        'chr_jobs_pending': sum(bool(value) for value in ram[0x1D80:0x1D98]),
                        'game_nmi_ticks_010b': ram[0x10B],
                        'scroll_x':ram[0x1C28], 'scroll_y':ram[0x1C29],
                        'logical_camera_x': int.from_bytes(ram[0xDC:0xDE], 'little'),
                        'hdma_street_scroll_x': ram[0x1C94] | ((ram[0x1C95] & 1) << 8),
                        'deferred_game_nmi_pending': ram[0x1CE0],
                        'deferred_game_nmi_iteration': ram[0x1CE1],
                        'deferred_game_nmi_scheduled': int.from_bytes(ram[0x1CE2:0x1CE4], 'little'),
                        'deferred_game_nmi_served': int.from_bytes(ram[0x1CE4:0x1CE6], 'little'),
                        'deferred_game_nmi_fallback': int.from_bytes(ram[0x1CE6:0x1CE8], 'little'),
                        'deferred_game_nmi_armed': ram[0x1CEB],
                        'publish_count':ram[0x1C7A], 'apu_packet':ram[0xA00:0xA17].hex()}
                    if boot_monitor is not None:
                        raw = registers(ram)
                        active, fault = boot_monitor.observe(rows[-1]['native']['pc'], raw)
                        rows[-1].update(fault_registers=raw, adapter_monitor_active=active, fault=fault)
                if frame_images:
                    directory = out/'frames'
                    directory.mkdir(exist_ok=True)
                    filename = f'frame-{len(rows):05d}.png'
                    Image.fromarray(latest).save(directory/filename)
                    rows[-1]['frame_image'] = 'frames/'+filename
                    rows[-1]['frame_image_sha256'] = sha(directory/filename)
                if background:
                    raw,pitch,bg_format,flags=background.read()
                    rgb=decode_frame(raw,256,240,pitch,bg_format)
                    filename=f'background/frame-{len(rows):05d}.png'
                    Image.fromarray(rgb).save(out/filename)
                    rows[-1]['background']={'image':filename,'sha256':sha(out/filename),
                        'rgb_sha256':hashlib.sha256(rgb.tobytes()).hexdigest(),'valid_lines':flags.hex()}
                if has_waypoints:
                    rows[-1]['waypoint_cursor']=policy.cursor_mask(latest)
                pcm.extend(frame_audio)
                if 'waypoint' in phase:
                    stable=stable+1 if policy.reached(phase['waypoint'],ram[:2048],rows[-1]['waypoint_cursor']) else 0
                    if stable>=3:
                        matched=True
                        break
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
                             "frames": len(rows)-start, "transition_matched": matched if "until" in phase or 'waypoint' in phase else None,
                             "screenshot": f"{name}.png", "screenshot_sha256": snapshots[name],
                             "ram_snapshot": f"{name}.ram", "ram_snapshot_sha256": sha(out / f'{name}.ram')})
            if (scenario_name.startswith('traversal') or scenario_name in ('pause-cursor-return','pause-status','pause-status-after-combat')) and system == 'snes':
                vram_size, vram_ptr = core.retro_get_memory_size(3), core.retro_get_memory_data(3)
                if not vram_ptr or vram_size != 65536:
                    raise RuntimeError('Missing SNES video RAM evidence')
                (out/f'{name}.vram').write_bytes(C.string_at(vram_ptr, vram_size))
                segments[-1].update(vram_snapshot=f'{name}.vram',
                                    vram_snapshot_sha256=sha(out/f'{name}.vram'))
                if scenario_name.startswith('traversal-waypoint-shop') or scenario_name in ('traversal-shop-confirm', 'traversal-shop-repeat', 'traversal-shop-no', 'pause-cursor-return','pause-status','pause-status-after-combat'):
                    if size != 128 * 1024:
                        raise RuntimeError('Missing full WRAM for shop nametable diagnosis')
                    # Read-only raw NES CIRAM shadow ($7F:2000..27FF), which
                    # separates missing game writes from lost SNES publication.
                    shadow = C.string_at(ptr + 65536 + 0x2000, 0x800)
                    (out/f'{name}.nametable').write_bytes(shadow)
                    segments[-1].update(nametable_snapshot=f'{name}.nametable',
                                        nametable_snapshot_sha256=sha(out/f'{name}.nametable'))
            elif (scenario_name.startswith('traversal-waypoint-shop') or scenario_name in ('traversal-shop-confirm', 'traversal-shop-repeat', 'traversal-shop-no', 'pause-cursor-return','pause-status','pause-status-after-combat')) and system == 'nes':
                # The pinned diagnostic FCEUmm build exposes its physical
                # 2 KiB CIRAM read-only via RETRO_MEMORY_VIDEO_RAM.
                vram_size, vram_ptr = core.retro_get_memory_size(3), core.retro_get_memory_data(3)
                if not vram_ptr or vram_size != 2048:
                    raise RuntimeError('Missing original NES CIRAM diagnostic')
                (out/f'{name}.nametable').write_bytes(C.string_at(vram_ptr, vram_size))
                segments[-1].update(nametable_snapshot=f'{name}.nametable',
                                    nametable_snapshot_sha256=sha(out/f'{name}.nametable'))
            if ("until" in phase or 'waypoint' in phase) and not matched:
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
                  "frame_images": frame_images,
                  "full_ram_telemetry": full_ram_telemetry,
                  "scenario": scenario, "scenario_sha256": hashlib.sha256(json.dumps(scenario, sort_keys=True).encode()).hexdigest(),
                  "input_mapping": MAPPING[system], "core_options": {k.decode(): v.decode() for k,v in options.items()},
                  "fps": av.timing.fps, "sample_rate": av.timing.sample_rate,
                  "segments": segments, "audio_sha256": sha(out / "audio.wav"),
                  "timeline_sha256": sha(out / "timeline.json"), "frames": len(rows),
                  "capture_complete": len(segments) == len(scenario) and all(s["transition_matched"] is not False for s in segments),
                  "release_ready": False}
        if boot_policy is not None:
            report['boot_fault_policy'] = boot_policy
        if background:
            if background_hashes!={str(p.relative_to(ROOT)):sha(p) for p in background_sources(ROOT,system)}:
                raise ValueError('Background observer sources changed during capture')
            report['background_observer']={'schema':'rcr-background-v1','sources':background_hashes,
                'scope':'Additional diagnostic background plane; primary video and emulated state unchanged.'}
        if ppu_telemetry:
            report['nes_ppu_observer'] = dict(method='libretro-PPUREG-read-only',
                source_sha256=sha(Path(__file__).with_name('libretro_memory.py')))
        if palette_telemetry:
            report['snes_palette_observer'] = dict(method='libretro-WRAM-palette-read-only',
                source_sha256=sha(Path(__file__).with_name('palette_telemetry.py')))
        if any('waypoint' in p for p in scenario):
            report['waypoint_policy_sha256']=sha(Path(policy.__file__))
            if getattr(policy, 'SOURCE_FILES', ()):
                report['waypoint_dependency_sha256']={p.name:sha(p) for p in policy.SOURCE_FILES}
        # The ACK observer flushes every row; bind that host-only observation
        # to the same fresh process, ROM, core, inputs and execution timeline.
        ack_path = os.environ.get('RCR_SPC_ACK_TRACE')
        if ack_path:
            report['spc_ack_trace'] = {'path': str(Path(ack_path).resolve()),
                                      'sha256': sha(Path(ack_path))}
        bus_path = os.environ.get('RCR_AUDIO_BUS_TRACE')
        if bus_path:
            report['audio_bus_trace'] = dict(path=str(Path(bus_path).resolve()),sha256=sha(Path(bus_path)))
        span_path = os.environ.get('RCR_SPAN_TRACE')
        if span_path:
            report['span_trace'] = {'path': str(Path(span_path).resolve()),
                                    'sha256': sha(Path(span_path)),
                                    'points': {str(i):os.environ[f'RCR_SPAN_PC{i}'] for i in range(16)
                                               if f'RCR_SPAN_PC{i}' in os.environ},
                                    'first':int(os.environ.get('RCR_PROFILE_FIRST','0')),
                                    'last':int(os.environ.get('RCR_PROFILE_LAST','0'))}
        instruction_path = os.environ.get('RCR_INSTRUCTION_TRACE')
        if instruction_path:
            report['instruction_trace'] = dict(path=str(Path(instruction_path).resolve()),
                sha256=sha(Path(instruction_path)),
                first=int(os.environ.get('RCR_PROFILE_FIRST','0')),
                last=int(os.environ.get('RCR_PROFILE_LAST','0')))
        render_path = os.environ.get('RCR_RENDER_SCROLL_TRACE')
        if render_path:
            # These separate diagnostic cores buffer host stdio. Flush before
            # binding the complete trace to this process's ROM/core/replay.
            flush = C.CDLL(None).fflush
            flush.argtypes = [C.c_void_p]
            flush.restype = C.c_int
            if flush(None) != 0:
                raise ValueError('Cannot flush renderer observation')
            report['render_scroll_trace'] = dict(path=str(Path(render_path).resolve()),
                sha256=sha(Path(render_path)),
                first=int(os.environ.get('RCR_RENDER_FIRST','7600')),
                last=int(os.environ.get('RCR_RENDER_LAST','8420')))
        report.update(bind_spc_observations(os.environ))
        nes_event_path = os.environ.get('RCR_NES_EVENT_TRACE')
        if nes_event_path:
            if system != 'nes':
                raise ValueError('NES event trace requires NES capture')
            try:
                from .nes_event_trace import validate_file as validate_events
            except ImportError:
                from nes_event_trace import validate_file as validate_events
            first=int(os.environ.get('RCR_NES_TRACE_FIRST','0'))
            last=int(os.environ.get('RCR_NES_TRACE_LAST','0'))
            points={str(i):os.environ[f'RCR_NES_EVENT_PC{i}'] for i in range(8)
                    if f'RCR_NES_EVENT_PC{i}' in os.environ}
            observed=validate_events(Path(nes_event_path),first,last,len(rows),points)
            report['nes_event_trace']=dict(path=str(Path(nes_event_path).resolve()),
                sha256=sha(Path(nes_event_path)),first=first,last=last,points=points,**observed,
                validator_sha256=sha(Path(__file__).with_name('nes_event_trace.py')),
                observer_sha256=sha(Path(__file__).with_name('fceumm_queue_trace.inc')))
        nes_scroll_path = os.environ.get('RCR_NES_SCROLL_TRACE')
        if nes_scroll_path:
            if system != 'nes':
                raise ValueError('NES scroll trace requires NES capture')
            try:
                from .nes_scroll_trace import validate_file
            except ImportError:
                from nes_scroll_trace import validate_file
            window_first=int(os.environ.get('RCR_NES_TRACE_FIRST', '6500'))
            window_last=int(os.environ.get('RCR_NES_TRACE_LAST', '7100'))
            observed=validate_file(Path(nes_scroll_path),window_first,window_last,len(rows))
            # The pinned CPU write observer flushes each record. Bind at the
            # end of this very capture, not later in a separate report step.
            report['nes_scroll_trace'] = dict(path=str(Path(nes_scroll_path).resolve()),
                sha256=sha(Path(nes_scroll_path)),
                first=window_first,last=window_last,**observed,
                window_validator_sha256=sha(Path(__file__).with_name('nes_scroll_trace.py')),
                observer_sha256=sha(Path('.deps/fceumm/src/x6502.c')))
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
    parser.add_argument('--frame-images', action='store_true', help='Retain every rendered frame with PNG and raw-pixel hashes')
    parser.add_argument('--full-ram-telemetry', action='store_true', help='Retain the original game\'s 2 KiB RAM for every frame for deterministic transition profiling')
    parser.add_argument('--ppu-telemetry',action='store_true',help='Read actual NES PPU registers through the core-provided memory map')
    parser.add_argument('--palette-telemetry',action='store_true',help='Read native palette shadow and prepared snapshots from core-advertised SNES WRAM')
    parser.add_argument('--background-telemetry',action='store_true',help='Retain a diagnostic background plane from an observer core')
    parser.add_argument('--scenario',choices=('baseline','combat-knockdown-audio','movement-probe','menu-audio','start','select','start-select','start-confirm','traversal','traversal-recovery','traversal-upper','traversal-jump','traversal-jump-lower','traversal-mall','traversal-shop','traversal-shop-exit','traversal-park-stress','traversal-park-coverage','traversal-park-single-sweep','traversal-expanded-sweep','traversal-shop-confirm','traversal-shop-repeat','traversal-shop-no','traversal-waypoint-shop','traversal-waypoint-shop-repeat','traversal-waypoint-shop-no','controls-presets','pause-cursor-return','pause-status','pause-status-after-combat'),default='baseline')
    args = parser.parse_args()
    refs = {"menu": (args.title, 600), "settings": (args.walk, 600),
            "story": (args.walk, 900), "street": (args.walk, 1800)}
    capture(args.core, args.rom, args.system, refs, args.out, args.scenario, args.frame_images,
            args.full_ram_telemetry, args.ppu_telemetry, args.palette_telemetry,args.background_telemetry)
