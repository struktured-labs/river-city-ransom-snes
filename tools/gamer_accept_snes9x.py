"""Gamer Mode acceptance checklist in headless snes9x (libretro, ctypes).

Second-emulator companion to tools/mesen/accept.lua. snes9x does not expose
PPU OAM/CGRAM or memory callbacks, so the outline check here compares the
game's NES OAM marks with the SNES OAM shadow ($7E5000) and the palette
shadow, and counts red pixels on goons in screenshots. Actor ownership of
each sprite is audited in Mesen2, which can watch the metasprite writer.

usage: python3 -m tools.gamer_accept_snes9x ROM OUTDIR
"""
import ctypes as C
import sys
from pathlib import Path

from PIL import Image

CORE = Path('.deps/snes9x/libretro/snes9x_libretro.so')
B, Y, SELECT, START, UP, DOWN, LEFT, RIGHT, A = 0, 1, 2, 3, 4, 5, 6, 7, 8
NEXT = {1: 4, 4: 2, 2: 3, 3: 1}
PREV = {1: 3, 3: 2, 2: 4, 4: 1}
NAMES = {1: '00cdced5c8c2c400', 2: 'c0c3d5c0cdc2c4c3', 3: '00c6c0ccc4d10000', 4: 'c8cdd3c4d1ccc4c3'}
# Weapon/item tiles on the test route (rooms 00-01): tiles Mesen2's accept.lua
# saw drawn by weapon/item objects (sprite kind $08-$11) or by held-object
# parts ($FC branch at $EE4B), and never by an enemy body sprite ("item tiles"
# log line). snes9x has no write callbacks, so ownership is judged by tile.
ITEM_TILES = {0xD0, 0xDC, 0xDD, 0xE0, 0xEC, 0xED, 0xEE, 0xFE}
PATS = {'GAMER': 'c6c0ccc4d1', 'NOVICE': 'cdced5c8c2c4', 'ADVANCED': 'c0c3d5c0cdc2c4c3',
        'INTERMED': 'c8cdd3c4d1ccc4c3'}


class Game(C.Structure):
    _fields_ = [("path", C.c_char_p), ("data", C.c_void_p), ("size", C.c_size_t), ("meta", C.c_char_p)]


class Variable(C.Structure):
    _fields_ = [("key", C.c_char_p), ("value", C.c_char_p)]


class Emu:
    def __init__(self, rom, out):
        self.out = out
        self.core = core = C.CDLL(str(CORE.resolve()))
        self.held = {}
        self.frame = 0
        self.shot = None
        self.fmt = 1
        sysdir = str(out.resolve()).encode()

        @C.CFUNCTYPE(C.c_bool, C.c_uint, C.c_void_p)
        def environment(cmd, data):
            if cmd in (9, 31):
                C.cast(data, C.POINTER(C.c_char_p))[0] = sysdir
                return True
            if cmd == 10:
                self.fmt = C.cast(data, C.POINTER(C.c_int))[0]
                return True
            if cmd == 15:
                var = C.cast(data, C.POINTER(Variable)).contents
                if var.key == b'snes9x_overscan':
                    var.value = b'disabled'
                    return True
                return False
            if cmd in (3, 17):
                C.cast(data, C.POINTER(C.c_bool))[0] = cmd == 3
                return True
            return False

        @C.CFUNCTYPE(None, C.c_void_p, C.c_uint, C.c_uint, C.c_size_t)
        def video(data, w, h, pitch):
            if data and w and h:
                self.shot = (w, h, pitch, self.fmt, C.string_at(data, pitch * h))

        @C.CFUNCTYPE(None, C.c_int16, C.c_int16)
        def audio(l, r):
            return None

        @C.CFUNCTYPE(C.c_size_t, C.POINTER(C.c_int16), C.c_size_t)
        def batch(d, n):
            return n

        @C.CFUNCTYPE(None)
        def poll():
            return None

        @C.CFUNCTYPE(C.c_int16, C.c_uint, C.c_uint, C.c_uint, C.c_uint)
        def state(port, dev, idx, ident):
            return self.held.get(ident, 0) if port == 0 and dev == 1 else 0

        self._cb = (environment, video, audio, batch, poll, state)
        for name, cb in zip(('environment', 'video_refresh', 'audio_sample', 'audio_sample_batch',
                             'input_poll', 'input_state'), self._cb):
            fn = getattr(core, 'retro_set_' + name)
            fn.argtypes = [type(cb)]
            fn.restype = None
            fn(cb)
        core.retro_load_game.argtypes = [C.POINTER(Game)]
        core.retro_load_game.restype = C.c_bool
        core.retro_get_memory_data.argtypes = [C.c_uint]
        core.retro_get_memory_data.restype = C.c_void_p
        core.retro_get_memory_size.argtypes = [C.c_uint]
        core.retro_get_memory_size.restype = C.c_size_t
        core.retro_init()
        payload = Path(rom).read_bytes()
        self._data = C.create_string_buffer(payload)
        game = Game(str(Path(rom).resolve()).encode(), C.cast(self._data, C.c_void_p), len(payload), None)
        if not core.retro_load_game(C.byref(game)):
            raise SystemExit('load failed')
        self.wram_ptr = core.retro_get_memory_data(2)
        self.vram_ptr = core.retro_get_memory_data(3)

    def ram(self):
        return C.string_at(self.wram_ptr, 0x20000)

    def rd(self, a):
        return C.cast(self.wram_ptr, C.POINTER(C.c_ubyte))[a]

    def wr(self, a, v):
        C.cast(self.wram_ptr, C.POINTER(C.c_ubyte))[a] = v

    def vram(self):
        return C.string_at(self.vram_ptr, 0x10000)

    def step(self, n=1):
        for _ in range(n):
            self.core.retro_run()
            self.frame += 1

    def press(self, ident, on=6, off=20):
        self.held[ident] = 1
        self.step(on)
        self.held[ident] = 0
        self.step(off)

    def png(self, name):
        w, h, pitch, fmt, raw = self.shot
        px = bytearray()
        for y in range(h):
            for x in range(w):
                o = y * pitch + x * (4 if fmt == 1 else 2)
                v = int.from_bytes(raw[o:o + (4 if fmt == 1 else 2)], 'little')
                if fmt == 1:
                    px += bytes(((v >> 16) & 255, (v >> 8) & 255, v & 255))
                else:
                    px += bytes((((v >> 11) & 31) * 255 // 31, ((v >> 5) & 63) * 255 // 63, (v & 31) * 255 // 31))
        img = Image.frombytes('RGB', (w, h), bytes(px))
        path = self.out / f'{name}.png'
        img.save(path)
        return img, path


def main(rom, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    e = Emu(rom, out)
    fails = []
    logf = open(out / 'log.txt', 'w')

    def log(*a):
        line = f'[f{e.frame:06d}] ' + ' '.join(str(x) for x in a)
        print(line, flush=True)
        logf.write(line + '\n')

    def check(name, ok, detail=''):
        log('PASS' if ok else 'FAIL', name, detail)
        if not ok:
            fails.append(name)

    def st():
        r = e.rd
        return (f'mode={r(6):02x} 100={r(0x100):02x} CA0={r(0x1CA0):02x} 3F={r(0x3F):02x} '
                f'sk={r(0x64C):02x} stam={r(0x4BF):02x}')

    def title():
        r = e.rd
        return r(6) == 0x3D and r(0x100) == 0x80 and r(0x1CA0) == 0 and r(0x1212F) == 0xCF and r(0x12130) == 0xCB

    def settings():
        return e.rd(6) == 5 and e.rd(0x1CA0) == 0

    def street():
        return (e.rd(0x100) & 0xC0) == 0xC0 and e.rd(6) != 5 and e.rd(0x1CA0) == 0

    def wait(pred, n):
        for _ in range(n):
            if pred():
                return True
            e.step()
        return pred()

    def vname():
        v = e.vram()
        return bytes(v[(0x22AC + i) * 2] for i in range(8)).hex()

    def find_names():
        v = e.vram()
        tiles = bytes(v[w * 2] for w in range(0x2000, 0x3000)).hex()
        shadow = e.ram()[0x12000:0x13000].hex()
        hits = []
        for n, p in PATS.items():
            for label, s in (('VRAM', tiles), ('SHADOW', shadow)):
                i = s.find(p)
                while i >= 0:
                    if i % 2 == 0:
                        hits.append(f'{label}:{n}@{0x2000 + i // 2:04x}')
                    i = s.find(p, i + 1)
        return hits

    # 1. skill
    if not wait(title, 2400):
        check('reach title', False, st())
        return fails
    e.press(START, 12, 18)
    if not wait(settings, 600):
        check('reach settings', False, st())
        return fails
    e.step(20)
    step_fail = name_fail = 0

    def tap(ident, on, off):
        nonlocal step_fail
        b = e.rd(0x64C)
        e.press(ident, on, off)
        want = NEXT[b] if ident == RIGHT else PREV[b]
        if e.rd(0x64C) != want:
            step_fail += 1
            log('step fail', ident, on, off, b, e.rd(0x64C), want)

    def settle(tag):
        nonlocal name_fail
        e.step(10)
        sk = e.rd(0x64C)
        if vname() != NAMES[sk] or e.ram()[0x122AC:0x122B4].hex() != NAMES[sk]:
            name_fail += 1
            log('name fail', tag, sk, vname())

    settle('initial')
    for _ in range(4):
        tap(RIGHT, 6, 20)
        settle('R')
    for _ in range(4):
        tap(LEFT, 6, 20)
        settle('L')
    for on, off in ((2, 2), (2, 1), (1, 1), (1, 2), (3, 1), (4, 2)):
        for _ in range(4):
            tap(RIGHT, on, off)
        settle(f'qR{on}/{off}')
        for _ in range(3):
            tap(LEFT, on, off)
        settle(f'qL{on}/{off}')
    while e.rd(0x64C) != 3:
        tap(RIGHT, 6, 20)
    settle('gamer')
    e.png('1-skill-gamer')
    check('1 skill: one step per press', step_fail == 0, f'stepFails={step_fail}')
    check('1 skill: name on screen matches memory', name_fail == 0, f'nameFails={name_fail}')
    # 2. Start
    for _ in range(4):
        tap(RIGHT, 2, 1)
    e.press(START, 3, 1)
    moved = False
    for _ in range(40):
        e.step(15)
        if e.rd(6) != 5:
            moved = True
    e.png('2-after-start')
    for _ in range(60):
        if street():
            break
        e.press(A, 8, 12)
    check('2 Start proceeds and reaches the street', moved and street(), st())
    e.step(30)
    check('3 no skill name on street at start', not find_names(), ' '.join(find_names()))
    e.png('3-street-start')

    hist = []
    items = dict(spr=0, red=0, heldFrames=0, groundFrames=0, heldShots=0, groundShots=0)

    def outline_audit(stats):
        # The SNES OAM shadow is filled by the game's next OAM copy, so it may
        # hold any of the last few frames' NES attributes.
        r = e.ram()
        cur = [r[0x202 + i * 4] for i in range(64)]
        for i in range(64):
            y, tile, attr, x = r[0x200 + i * 4:0x204 + i * 4]
            if y >= 0xEF:
                continue
            snes = r[0x5003 + i * 4] & 0xFE
            stats['pairs'] += 1
            wants = []
            for a in [cur[i]] + [h[i] for h in hist]:
                wants.append((a & 0xC0) | ((a & 3) << 1) | (0 if a & 0x20 else 0x30) | (8 if a & 4 else 0))
            if snes not in wants:
                stats['mismatch'] += 1
            if attr & 4:
                stats['marked'] += 1
            if tile in ITEM_TILES:
                items['spr'] += 1
                if attr & 4:
                    items['red'] += 1
        # scenario screenshots: a goon holding a weapon, a weapon on the ground
        for s in range(2, 8):
            kind, fl, p = r[0xCB + s], r[0x56 + s], r[0x3B7 + s]
            if kind < 8 and fl & 0x40 and p < 8 and 8 <= r[0xCB + p] <= 0x11 and r[0x3B7 + p] == s:
                items['heldFrames'] += 1
                if items['heldShots'] < 2 and e.frame % 90 == 0:
                    items['heldShots'] += 1
                    e.png(f"8-goon-holding-weapon-{items['heldShots']}")
            if 8 <= kind <= 0x11 and not fl & 0x40 and (r[0xD3 + s] & 0x7F) != 0x7F:
                items['groundFrames'] += 1
                if items['groundShots'] < 2 and e.frame % 90 == 0:
                    items['groundShots'] += 1
                    e.png(f"8-weapon-on-ground-{items['groundShots']}")
        hist.insert(0, cur)
        del hist[3:]
        stats['frames'] += 1

    def red_pixels(img):
        # native_palette[$16] = $00BB -> 5-bit R=27 G=5 B=0
        return sum(1 for p in img.getdata() if p[0] > 200 and p[1] < 70 and p[2] < 30)

    stats = dict(frames=0, pairs=0, mismatch=0, marked=0)
    alive_fail = 0
    last = None
    same = 0
    name_hits = 0
    reds = []
    for sec in range(1, 71):
        for f in range(60):
            ph = (e.frame // 20) % 6
            e.held = {RIGHT: int(sec % 10 < 6), LEFT: int(sec % 10 >= 8), Y: int(ph == 1), B: int(ph == 3)}
            e.step()
            outline_audit(stats)
            if f % 15 == 0:
                key = (e.rd(0x52B), e.ram()[0x200:0x300])
                same = same + 1 if key == last else 0
                last = key
                if same >= 8:
                    alive_fail += 1
        if find_names():
            name_hits += 1
        if sec % 10 == 0:
            img, _ = e.png(f'7-street-{sec:02d}s')
            reds.append(red_pixels(img))
            log('sec', sec, st(), 'types', e.ram()[0x4F5:0x4FD].hex(), 'red px', reds[-1])
    e.held = {}
    log('outline', stats)
    check('3 no skill name during play', name_hits == 0, f'hits={name_hits}')
    check('4 NES goon marks carried to SNES OAM; red outline visible',
          stats['mismatch'] == 0 and stats['marked'] > 0 and max(reds) > 0, f'{stats} red={reds}')
    check('7 no freeze in 70 s of street play', alive_fail == 0 and street(), st())
    # 5. pause, with marked goons on screen
    for i in range(900):
        r = e.ram()
        if sum(1 for k in range(64) if r[0x200 + k * 4] < 0xEF and r[0x202 + k * 4] & 4) >= 4:
            break
        e.held = {RIGHT: int(i % 120 < 60), LEFT: int(i % 120 >= 90)}
        e.step()
    e.held = {}
    e.step(2)
    before = e.ram()[0x5500:0x5580]
    img, _ = e.png('5-before-pause')
    red_before = red_pixels(img)
    e.press(START, 6, 2)
    saw = False
    for _ in range(120):
        e.step()
        saw = saw or e.rd(0x3F) != 0
    img, _ = e.png('5-paused')
    red_paused = red_pixels(img)
    e.press(START, 6, 2)
    e.step(120)
    e.png('5-after-unpause')
    same_pal = e.ram()[0x5500:0x5580] == before
    stats = dict(frames=0, pairs=0, mismatch=0, marked=0)
    for i in range(240):
        e.held = {RIGHT: int(i % 60 < 30)}
        e.step()
        outline_audit(stats)
    e.held = {}
    check('5 pause/unpause keeps marks and palettes', saw and same_pal and stats['mismatch'] == 0
          and stats['marked'] > 0 and red_before > 0 and red_paused > 0,
          f'saw={saw} samePal={same_pal} red before/paused={red_before}/{red_paused} {stats}')
    # 6. low stamina
    stats = dict(frames=0, pairs=0, mismatch=0, marked=0)
    for i in range(240):
        e.wr(0x4BF, 2)
        e.held = {RIGHT: int(i % 40 < 20), Y: int(i % 20 == 5)}
        e.step()
        outline_audit(stats)
    img, _ = e.png('6-low-stamina')
    check('6 marks persist at low stamina', stats['mismatch'] == 0 and stats['marked'] > 0,
          f'{stats} red={red_pixels(img)}')
    check('8 no weapon/item sprite outlined (ground and held by a goon)',
          items['red'] == 0 and items['spr'] > 0 and items['heldFrames'] > 0 and items['groundFrames'] > 0,
          f'{items}')
    log('DONE fails', len(fails), fails)
    return fails


if __name__ == '__main__':
    sys.exit(1 if main(sys.argv[1], sys.argv[2]) else 0)
