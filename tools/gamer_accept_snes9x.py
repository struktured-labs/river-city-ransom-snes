"""Gamer Mode acceptance checklist in headless snes9x (libretro, ctypes).

Second-emulator companion to tools/mesen/accept.lua. snes9x does not expose
PPU OAM/CGRAM or memory callbacks, so the outline check here compares the
game's NES OAM marks with the SNES OAM shadow ($7E5000) and the palette
shadow, and counts red pixels on goons in screenshots. Actor ownership of
each sprite is audited in Mesen2, which can watch the metasprite writer.

usage: python3 -m tools.gamer_accept_snes9x ROM OUTDIR
"""
import ctypes as C
import itertools
import os
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
# red share of the composed silhouette-edge outline pixels (as accept.lua)
COVERAGE_MIN = 80
CARRY_WAITS = (2, 11, 23, 0, 4, 28, 37, 43, 6, 1, 3, 5, 7, 8, 9, 10, 12, 13, 14, 15)
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
        core.retro_reset.restype = None
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

    def carry_attempt(wait_frames):
        # 9. Alex carries a knocked-down goon (route of accept.lua carryPhase):
        # from a fresh boot, walk to the nearest goon and punch; punch over a
        # lying goon ($4F state $11/$12) picks it up, punch again throws it.
        # Without write callbacks the carried goon's sprites are found by place:
        # while Alex carries ($56 bit 6, $03B7,0 = goon, goon $4F = $15), shirt
        # sprites (NES palette 3; Alex's torso is palette 0) in a box around
        # Alex and away from every other goon are the carried goon's.
        for a_ in range(0x20000):     # work RAM as at power-on, then reset
            e.wr(a_, 0)
        e.core.retro_reset()
        e.held = {}
        if not wait(title, 2400):
            check('9 reach title after reset', False, st())
            return None
        e.press(START, 12, 18)
        if not wait(settings, 600):
            check('9 reach settings after reset', False, st())
            return None
        e.step(20)
        e.wr(0x64C, 1)                # the skill survives a reset
        while e.rd(0x64C) != 3:
            e.press(RIGHT, 6, 20)
        # frames to wait on the skill screen: picks the fight (the game's
        # random numbers run every frame)
        e.step(wait_frames)
        e.press(START, 3, 1)
        for _ in range(40):
            e.step(15)
        for _ in range(60):
            if street():
                break
            e.press(A, 8, 12)
        r8 = e.rd

        def px(sl):
            return r8(0x83 + sl) + 256 * r8(0x8C + sl)

        carry = dict(frames=0, judged=0, boxMarked=0, unredFrames=0, shots=0)
        carry_t = 0
        unstick = unstick_n = 0
        last_ax = None
        for f in range(1, 6001):
            e.wr(0x4BF, 0x7F)
            best, bd = None, 10 ** 9
            for sl in range(2, 8):
                if r8(0xCB + sl) < 8 and (r8(0xD3 + sl) & 0x7F) != 0x7F and px(sl) > 0:
                    d = abs(px(sl) - px(0))
                    if d < bd:
                        bd, best = d, sl
            h = {}
            g = r8(0x3B7)
            carrying = (r8(0x56) & 0x40) and 2 <= g <= 7 and r8(0xCB + g) < 8
            st4f = (r8(0x4F + best) & 0x7F) if best is not None else 0
            if carrying:
                carry_t += 1
                h[RIGHT if carry_t % 120 < 60 else LEFT] = 1
                if carry_t % 150 == 90:
                    h[Y] = 1
            elif best is not None and st4f in (0x11, 0x12):
                carry_t = 0
                dx, dy = px(best) - px(0), r8(0x9E + best) - r8(0x9E)
                if dx > 3:
                    h[RIGHT] = 1
                elif dx < -3:
                    h[LEFT] = 1
                if dy > 1:
                    h[DOWN] = 1
                elif dy < -1:
                    h[UP] = 1
                if abs(dx) <= 6 and abs(dy) <= 1 and f % 10 < 2:
                    h[Y] = 1
            elif best is not None:
                carry_t = 0
                dx, dy = px(best) - px(0), r8(0x9E + best) - r8(0x9E)
                if dx > 6:
                    h[RIGHT] = 1
                elif dx < -6:
                    h[LEFT] = 1
                if dy > 2:
                    h[DOWN] = 1
                elif dy < -2:
                    h[UP] = 1
                if abs(dx) <= 12 and abs(dy) <= 4 and f % 16 < 3:
                    h[Y] = 1
                if f % 40 == 20:
                    h[B] = 1
            else:
                h[RIGHT] = int(f % 200 < 150)
                if f % 40 == 20:
                    h[B] = 1
            # unstick (as in accept.lua): Alex moved less than 4 px in 90
            # frames while not carrying -> walk away diagonally for 60 frames
            ax0 = px(0)
            if f % 90 == 0:
                if not carrying and last_ax is not None and abs(ax0 - last_ax) < 4:
                    unstick, unstick_n = 60, unstick_n + 1
                last_ax = ax0
            if unstick > 0:
                unstick -= 1
                h = {UP: 1, LEFT: 1} if unstick_n % 2 == 1 else {DOWN: 1, RIGHT: 1}
            e.held = h
            e.step()
            if f % 300 == 0:
                log(f'carry phase f={f} best={best} dx={px(best) - px(0) if best is not None else 0} '
                    f'dy={r8(0x9E + best) - r8(0x9E) if best is not None else 0} '
                    f'goon4F={r8(0x4F + best) if best is not None else 0:02x} alexX={px(0)} '
                    f'alex4F={r8(0x4F):02x} carried={carry["frames"]}', st())
            r = e.ram()
            g = r[0x3B7]
            if r[0x56] & 0x40 and 2 <= g <= 7 and r[0xCB + g] < 8 and (r[0x4F + g] & 0x7F) == 0x15:
                carry['frames'] += 1
                scroll = r[0xDC] + 256 * r[0xDD]      # camera left edge (world x)
                ax, ay = px(0) - scroll, r[0x9E]
                others = [(px(sl) - scroll, r[0x9E + sl]) for sl in range(2, 8) if sl != g
                          and r[0xCB + sl] < 8 and (r[0xD3 + sl] & 0x7F) != 0x7F]
                # shirt sprites (NES palette 3; Alex's torso is palette 0) in a
                # box around Alex, away from every other goon: the carried goon
                shirts = [i for i in range(64) if r[0x200 + i * 4] < 0xEF
                          and r[0x202 + i * 4] & 3 == 3
                          and ax - 40 <= r[0x203 + i * 4] <= ax + 32
                          and ay - 56 <= r[0x200 + i * 4] <= ay + 16
                          and not any(abs(r[0x203 + i * 4] - ox) <= 32 and oy - 56 <= r[0x200 + i * 4] <= oy + 16
                                      for ox, oy in others)]
                if os.environ.get('RCR_CARRY_DEBUG') and carry['frames'] % 8 == 1:
                    box = [(r[0x203 + i * 4], r[0x200 + i * 4], r[0x202 + i * 4]) for i in range(64)
                           if r[0x200 + i * 4] < 0xEF and ax - 40 <= r[0x203 + i * 4] <= ax + 32]
                    log('carry dbg', ax, ay, px(0), others, sorted((r[0x203 + i * 4], r[0x200 + i * 4], r[0x202 + i * 4]) for i in range(64) if r[0x200 + i * 4] < 0xEF))
                if not shirts:
                    continue
                carry['judged'] += 1
                unred = sum(1 for i in shirts if not r[0x202 + i * 4] & 4)
                carry['boxMarked'] += len(shirts) - unred
                if unred:
                    carry['unredFrames'] += 1
                if carry['shots'] < 3 and carry['judged'] % 20 == 1:
                    carry['shots'] += 1
                    e.png(f"9-alex-carrying-goon-{carry['shots']}")
            if carry['judged'] > 40 and f > 1200:
                break
        e.held = {}
        return carry

    def carry_check():
        # The route does not always get a goon down in snes9x; try a few
        # fights (fixed list, same for every build) until one is carried.
        waits = [int(os.environ['RCR_CARRY_WAIT'])] if 'RCR_CARRY_WAIT' in os.environ else CARRY_WAITS
        carry = None
        for n in waits:
            carry = carry_attempt(n)
            if carry is None:
                return
            log('carry attempt', n, carry)
            if carry['judged'] >= 20:
                break
        check('9 a goon carried by Alex keeps its red outline',
              carry['judged'] > 0 and carry['unredFrames'] == 0, f'{carry}')

    if os.environ.get('RCR_ONLY_CARRY'):
        carry_check()
        log('DONE fails', len(fails), fails)
        return fails
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
                wants.append((a & 0xC0) | ((a & 3) << 1) | (0 if a & 0x20 else 0x30) | (8 if a & 4 and a & 3 != 2 else 0))
            if snes not in wants:
                stats['mismatch'] += 1
            if attr & 4:
                stats['marked'] += 1
            if tile in ITEM_TILES:
                items['spr'] += 1
                if attr & 4:
                    items['red'] += 1
        # scenario screenshots: a goon holding a weapon, a weapon on the ground
        # (only when a marked goon and an item tile are both on screen)
        vis = [i for i in range(64) if r[0x200 + i * 4] < 0xEF]
        on_screen = (any(r[0x202 + i * 4] & 4 for i in vis)
                     and any(r[0x201 + i * 4] in ITEM_TILES for i in vis))
        for s in range(2, 8):
            kind, fl, p = r[0xCB + s], r[0x56 + s], r[0x3B7 + s]
            if kind < 8 and fl & 0x40 and p < 8 and 8 <= r[0xCB + p] <= 0x11 and r[0x3B7 + p] == s:
                items['heldFrames'] += 1
                if on_screen and items['heldShots'] < 2 and e.frame % 90 == 0:
                    items['heldShots'] += 1
                    e.png(f"8-goon-holding-weapon-{items['heldShots']}")
            if 8 <= kind <= 0x11 and not fl & 0x40 and (r[0xD3 + s] & 0x7F) != 0x7F:
                items['groundFrames'] += 1
                if on_screen and items['groundShots'] < 2 and e.frame % 90 == 0:
                    items['groundShots'] += 1
                    e.png(f"8-weapon-on-ground-{items['groundShots']}")
        # every sprite palette: color 5 (recolored outline) = color 1 in the
        # palette shadow the sprite palette DMA uploads
        if any(r[0x5502 + 32 * p:0x5504 + 32 * p] != r[0x550A + 32 * p:0x550C + 32 * p] for p in range(4)):
            stats['palBad'] = stats.get('palBad', 0) + 1
        if e.frame % 15 == 0:
            edge_audit(r)
            composed_audit(r)
        hist.insert(0, cur)
        del hist[3:]
        stats['frames'] += 1

    edge = dict(tiles=0, red=0, bad=0, pal6=0, plain=0, plainBad=0, redInside=0, darkEdge=0, darkInside=0,
                composedFrames=0, skipped=0, edgeOutline=0, edgeRed=0, redInsideComposed=0)

    def edge_audit(r):
        # Tile level, from VRAM, as in accept.lua: every visible sprite in the
        # SNES OAM shadow on a red palette (4, 5, 7) uses only indices 0-3 and
        # 5; red (5) only where a transparent pixel touches it in the tile
        # (outer silhouette, nothing red inside), and no color-1 pixel next to
        # a transparent one left dark. Plane 2 only on former index-1 pixels.
        # OBSEL = 2: sprite tiles at VRAM word $4000, second table +$1000.
        v = e.vram()
        for i in range(64):     # one SNES sprite per NES sprite
            y, tile, attr = r[0x5001 + i * 4], r[0x5002 + i * 4], r[0x5003 + i * 4]
            pal = (attr >> 1) & 7
            if y >= 0xE0:
                continue
            if pal == 6:
                edge['pal6'] += 1
                edge['bad'] += 1
            w = (0x4000 + (0x1000 if attr & 1 else 0) + tile * 16) & 0x7FFF
            b = v[w * 2:w * 2 + 32]
            if pal <= 3:
                # other sprites: plane 3 never set, plane 2 only on index 5,
                # which palettes 0-3 draw as color 1 (palBad)
                edge['plain'] += 1
                for rr in range(8):
                    p0, p1, p2, p3 = b[2 * rr], b[2 * rr + 1], b[16 + 2 * rr], b[17 + 2 * rr]
                    if p3 or p2 & ~(p0 & ~p1) & 0xFF:
                        edge['bad'] += 1
                        edge['plainBad'] += 1
                continue
            if pal not in (4, 5, 7):
                continue
            px = [[((b[2 * rr] >> (7 - c)) & 1) | (((b[2 * rr + 1] >> (7 - c)) & 1) << 1)
                   | (((b[16 + 2 * rr] >> (7 - c)) & 1) << 2) | (((b[17 + 2 * rr] >> (7 - c)) & 1) << 3)
                   for c in range(8)] for rr in range(8)]
            edge['tiles'] += 1
            for rr in range(8):
                for c in range(8):
                    val = px[rr][c]
                    near = [px[a_][d] for a_, d in ((rr - 1, c), (rr + 1, c), (rr, c - 1), (rr, c + 1))
                            if 0 <= a_ < 8 and 0 <= d < 8]
                    # in-tile view, reported only (a border pixel may be
                    # outer only across the border; see composed_audit)
                    if val == 5:
                        edge['red'] += 1
                        if 0 not in near:
                            edge['redInside'] += 1
                    elif val == 1:
                        if 0 in near:
                            edge['darkEdge'] += 1
                        else:
                            edge['darkInside'] += 1
                    elif val not in (0, 2, 3):
                        edge['bad'] += 1

    def composed_audit(r):
        # Composed silhouette, as compositeAudit in accept.lua, from the NES
        # OAM ($0200) with pixel indices from VRAM (sprite table 1, word
        # $5000). Without write callbacks each marked sprite is given to the
        # nearest enemy actor by screen x (base x as the metasprite writer
        # computes it); frames with two enemy actors within 64 px are skipped,
        # so one goon's body never counts as another's.
        scroll = r[0xDC] + 256 * r[0xDD]
        actors = []
        for sl in range(2, 8):
            if r[0xCB + sl] < 8 and (r[0xD3 + sl] & 0x7F) != 0x7F:
                bx = (r[0x83 + sl] + 256 * r[0x8C + sl] - scroll + r[0x3B]) & 0xFFFF
                actors.append((bx - 0x10000 if bx >= 0x8000 else bx, sl))
        if any(abs(a[0] - b[0]) < 64 for a, b in itertools.combinations(actors, 2)) or not actors:
            edge['skipped'] += 1
            return
        edge['composedFrames'] += 1
        v = e.vram()
        groups = {}
        for i in range(64):
            y, t, a, x = r[0x200 + i * 4], r[0x201 + i * 4], r[0x202 + i * 4], r[0x203 + i * 4]
            if y >= 0xEF or not a & 4 or a & 3 == 2:
                continue
            owner = min(actors, key=lambda ac: abs(ac[0] - x))[1]
            groups.setdefault(owner, []).append((x, y, t, a))
        for spr in groups.values():
            canvas = {}
            for x, y, t, a in spr:
                w = (0x5000 + t * 16) & 0x7FFF
                b = v[w * 2:w * 2 + 32]
                for rr in range(8):
                    ro = 7 - rr if a & 0x80 else rr
                    p0, p1, p2, p3 = b[2 * ro], b[2 * ro + 1], b[16 + 2 * ro], b[17 + 2 * ro]
                    for c in range(8):
                        sh = c if a & 0x40 else 7 - c
                        val = ((p0 >> sh) & 1) | (((p1 >> sh) & 1) << 1) | (((p2 >> sh) & 1) << 2) | (((p3 >> sh) & 1) << 3)
                        if val:
                            canvas.setdefault((x + c, y + rr), val)
            for (x, y), val in canvas.items():
                if val not in (1, 5):
                    continue
                if any(q not in canvas for q in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))):
                    edge['edgeOutline'] += 1
                    edge['edgeRed'] += val == 5
                elif val == 5:
                    edge['redInsideComposed'] += 1
                    edge['bad'] += 1

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
    edge['coverage'] = round(100 * edge['edgeRed'] / max(1, edge['edgeOutline']), 1)
    log('red edge', edge)
    check('4 NES goon marks carried to SNES OAM; red outline visible, only on the outer silhouette; '
          'color 5 = color 1 in every sprite palette',
          stats['mismatch'] == 0 and stats['marked'] > 0 and max(reds) > 0 and not stats.get('palBad')
          and edge['red'] > 0 and edge['bad'] == 0 and edge['coverage'] >= COVERAGE_MIN,
          f'{stats} red={reds} edge={edge} (coverage min {COVERAGE_MIN}%)')
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
    carry_check()
    log('DONE fails', len(fails), fails)
    return fails


if __name__ == '__main__':
    sys.exit(1 if main(sys.argv[1], sys.argv[2]) else 0)
