"""Rumble check in headless snes9x (second emulator, RAM only).

snes9x has no rumble device and no memory callbacks, so this follows the
helper's own state in WRAM ($7EF800-$7EF807, see snes/rumble.asm) through
scripted fights: pulses start on landed hits, hits taken and knockdowns,
the level always matches the pulse table, every pulse runs out and ends with
an off packet, and nothing runs on the title/settings screens or in pause.
The bus-level packet decoding (MiSTer core and Mesen2 semantics) is in
tools/mesen/rumble.lua.

usage: python3 -m tools.rumble_snes9x ROM OUTDIR
"""
import sys
from pathlib import Path

from tools.gamer_accept_snes9x import Emu, B, Y, START, UP, DOWN, LEFT, RIGHT, A
from tools.rumble_pulses import pulse_table, EVENTS, MAX_FRAMES

R = 0xF800
LAST, TIMER, LEVEL, RANK, OFF, EVENT, COUNT, SENT = range(8)


def main(rom, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    e = Emu(rom, out)
    table = pulse_table()
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

    r = e.rd
    rr = lambda o: e.rd(R + o)

    def gameplay():
        return r(0x3F) == 0 and r(6) != 5 and r(0xCC) == 0 and (r(0x100) & 0xC0) == 0xC0

    def title():
        return r(6) == 0x3D and r(0x100) == 0x80 and r(0x1CA0) == 0 and r(0x1212F) == 0xCF and r(0x12130) == 0xCB

    def street():
        return (r(0x100) & 0xC0) == 0xC0 and r(6) != 5 and r(0x1CA0) == 0

    S = dict(events={}, starts=0, badLevel=0, longPulse=0, menuActive=0, pauseActive=0, notOff=0, bad=[])
    track = dict(count=None, active=0)

    def observe(tag):
        c = rr(COUNT)
        if track['count'] is not None and c != track['count']:
            S['starts'] += (c - track['count']) & 0xFF
            ev = rr(EVENT)
            S['events'][EVENTS[ev] if ev < len(EVENTS) else ev] = S['events'].get(EVENTS[ev] if ev < len(EVENTS) else ev, 0) + 1
        track['count'] = c
        t = rr(TIMER)
        if t:
            rank = rr(RANK)
            if rank >= len(table) or rr(LEVEL) != (table[rank][1] << 4 | table[rank][2]) or t > table[rank][3]:
                S['badLevel'] += 1
                if len(S['bad']) < 5:
                    S['bad'].append(f'{tag} f{e.frame} t={t} rank={rank} lvl={rr(LEVEL):02x}')
            track['active'] += 1
            # a pulse of n game ticks lasts at most 2n video frames on the street (RCR's
            # game loop runs every second NMI) plus lag; 3 frames per tick is the bound
            if track['active'] > 3 * MAX_FRAMES:
                S['longPulse'] += 1
        else:
            track['active'] = 0

    def step(n=1, tag=''):
        for _ in range(n):
            e.step()
            observe(tag)

    def px(sl):
        return r(0x83 + sl) + 256 * r(0x8C + sl)

    st = dict(lastAx=None, unstick=0, n=0)

    def fight(frames, tag, force=None):
        for f in range(1, frames + 1):
            e.wr(0x4BF, 0x3F)
            if force == 'take':
                e.wr(0x497, 0x30)
            if force == 'ko':
                for s in range(2, 8):
                    if r(0x497 + s) > 4:
                        e.wr(0x497 + s, 4)
            if force == 'boss':
                for s in range(2, 8):
                    if r(0xCB + s) < 8 and r(0x4F5 + s) < 9:
                        e.wr(0x4F5 + s, 9)
                    if r(0xCB + s) < 8 and r(0x4BF + s) < 0x20:
                        e.wr(0x4BF + s, 0x40)   # keep forced bosses in the fight
            best, bd = None, 1e9
            for s in range(2, 8):
                if r(0xCB + s) < 8 and (r(0xD3 + s) & 0x7F) != 0x7F and px(s) > 0:
                    d = abs(px(s) - px(0))
                    if d < bd:
                        bd, best = d, s
            h = {}
            passive = (f % 600) >= 480 or force == 'take'
            if best is not None:
                dx, dy = px(best) - px(0), r(0x9E + best) - r(0x9E)
                lim = 10 if passive else 6
                if dx > lim:
                    h[RIGHT] = 1
                elif dx < -lim:
                    h[LEFT] = 1
                if dy > 2:
                    h[DOWN] = 1
                elif dy < -2:
                    h[UP] = 1
                if not passive:
                    if abs(dx) <= 12 and abs(dy) <= 4:
                        h[Y] = int(f % 16 < 3)
                    if f % 40 == 20:
                        h[B] = 1
            else:
                h[RIGHT] = int(f % 200 < 150)
            ax = px(0)
            if f % 90 == 0:
                if st['lastAx'] is not None and abs(ax - st['lastAx']) < 4:
                    st['unstick'] = 60
                    st['n'] += 1
                st['lastAx'] = ax
            if st['unstick'] > 0:
                st['unstick'] -= 1
                h = {UP: 1, LEFT: 1} if st['n'] % 2 else {DOWN: 1, RIGHT: 1}
            e.held = h
            step(1, tag)
        e.held = {}

    def press(ident, on, off, tag):
        e.held = {ident: 1}
        step(on, tag)
        e.held = {}
        step(off, tag)

    # title and settings
    for _ in range(2400):
        if title():
            break
        e.step()
    track['count'] = rr(COUNT)
    menu_active = 0
    press(START, 12, 18, 'title')
    for _ in range(60):
        step(1, 'settings')
        menu_active += rr(TIMER) != 0 or rr(SENT) != 0
    while r(0x64C) != 3:
        press(RIGHT, 6, 20, 'settings')
    press(START, 12, 18, 'settings')
    for _ in range(60):
        if street():
            break
        press(A, 8, 12, 'story')
    menu_starts = S['starts']
    check('S0 reached the street', street(), f'mode={r(6):02x}')
    fight(1200, 'take', 'take')
    fight(3000, 'fight')
    fight(1500, 'ko', 'ko')
    # pause right after a pulse starts
    pause_bad = 0
    saw_pause = 0
    for k in range(3):
        c = rr(COUNT)
        for _ in range(1200):
            fight(1, 'fight')
            if rr(COUNT) != c:
                break
        press(START, 3, 0, 'pause')
        for i in range(90):
            step(1, 'pause')
            if r(0x3F) != 0:
                saw_pause += 1
                if i > 8 and (rr(TIMER) != 0 or rr(OFF) != 0 or rr(SENT) != 0):
                    pause_bad += 1
        e.png(f'R-paused-{k + 1}')
        press(START, 3, 60, 'unpause')
    # boss rule: goon classes forced to a boss class (test only). Fight until the
    # phase has produced BOSS pulses (or time runs out), so the result does not
    # depend on whether this trajectory happens to meet a boss.
    boss0 = S['events'].get('BOSS', 0)
    for _ in range(8):
        fight(750, 'boss', 'boss')
        if S['events'].get('BOSS', 0) - boss0 >= 3:
            break
    boss_phase = S['events'].get('BOSS', 0) - boss0
    press(START, 3, 0, 'endpause')
    step(60, 'endpause')
    e.png('R-end-paused')
    end = dict(timer=rr(TIMER), off=rr(OFF), sent=rr(SENT))
    ev = S['events']
    log(f"starts={S['starts']} events={ev} badLevel={S['badLevel']} longPulse={S['longPulse']} "
        f"menuStarts={menu_starts} menuActive={menu_active} pauseFrames={saw_pause} pauseBad={pause_bad} end={end} {S['bad']}")
    check('S1 pulses on landed hits, hits taken and knockdowns',
          ev.get('LAND', 0) > 0 and ev.get('TAKE', 0) + ev.get('KNOCKDOWN', 0) > 0
          and ev.get('LAND_KO', 0) + ev.get('KNOCKDOWN', 0) > 0 and boss_phase > 0, f'{ev} bossPhase={boss_phase}')
    check('S2 level and length always from the pulse table', S['badLevel'] == 0 and S['longPulse'] == 0,
          f"badLevel={S['badLevel']} longPulse={S['longPulse']}")
    check('S3 every pulse ends with an off packet (timer 0, last level sent 0)',
          end == dict(timer=0, off=0, sent=0), f'{end}')
    check('S4 nothing on title/settings or in pause', menu_starts == 0 and menu_active == 0
          and saw_pause > 0 and pause_bad == 0,
          f'menuStarts={menu_starts} menuActive={menu_active} pauseFrames={saw_pause} pauseBad={pause_bad}')
    log('DONE fails', len(fails), fails)
    return fails


if __name__ == '__main__':
    sys.exit(1 if main(sys.argv[1], sys.argv[2]) else 0)
