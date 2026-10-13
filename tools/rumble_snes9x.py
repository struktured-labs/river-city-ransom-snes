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
import json

from tools.rumble_pulses import pulse_table, EVENTS, MAX_FRAMES, WEAPONS, weapon_pulse, KINDS

R = 0xF800
LAST, TIMER, LEVEL, RANK, OFF, EVENT, COUNT, SENT, DMG, ENV, WEAP, DMGU = range(12)
WEAPON_EVENTS = ('LAND', 'OBJECT', 'TAKE', 'LAND_KO')


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

    pulses = []           # one row per pulse start
    ticks = open(out / 'motor.csv', 'w')
    ticks.write('frame,phase,event,weapon,damage,timer,sent,strong,weak\n')
    S = dict(weapons={}, events={}, starts=0, badLevel=0, longPulse=0, menuActive=0, pauseActive=0, notOff=0, bad=[])
    track = dict(count=None, active=0)

    def observe(tag):
        c = rr(COUNT)
        if track['count'] is not None and c != track['count']:
            S['starts'] += (c - track['count']) & 0xFF
            ev = rr(EVENT)
            S['events'][EVENTS[ev] if ev < len(EVENTS) else ev] = S['events'].get(EVENTS[ev] if ev < len(EVENTS) else ev, 0) + 1
        started = track['count'] is not None and c != track['count']
        track['count'] = c
        t = rr(TIMER)
        if started:
            ev = EVENTS[rr(EVENT)] if rr(EVENT) < len(EVENTS) else '?'
            row = dict(frame=e.frame, phase=tag, event=ev, timer=t, level=rr(LEVEL), env=rr(ENV))
            if ev in WEAPON_EVENTS:
                w = WEAPONS[rr(WEAP)] if rr(WEAP) < len(WEAPONS) else '?'
                row.update(weapon=w, damage=rr(DMGU))
                key = f'{ev}/{w}'
                S['weapons'][key] = S['weapons'].get(key, 0) + 1
                lvl, n, env = weapon_pulse(w, ev, rr(DMGU)) if w != '?' else (None, None, None)
                # the first tick may already have run (decay lowers LEVEL, timer -1)
                okl = rr(LEVEL) in (lvl, (lvl or 0) - 0x10) and t in (n, (n or 0) - 1)
                row['expected'] = dict(level=lvl, ticks=n, env=env)
                if not okl:
                    S['badLevel'] += 1
                    if len(S['bad']) < 5:
                        S['bad'].append(row)
            pulses.append(row)
        if t:
            snt = rr(SENT)
            ticks.write(f"{e.frame},{tag},{EVENTS[rr(RANK)] if rr(RANK) < len(EVENTS) else '?'},"
                        f"{WEAPONS[rr(WEAP)] if rr(WEAP) < len(WEAPONS) else ''},{rr(DMGU)},{t},{snt},{snt >> 4},{snt & 15}\n")
        if t:
            rank = rr(RANK)
            if rank >= len(table) or EVENTS[rank] in WEAPON_EVENTS:
                pass
            elif rr(LEVEL) != (table[rank][1] << 4 | table[rank][2]) or t > table[rank][3]:
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
            if force and force.startswith('kind'):
                k = int(force[4:], 16)
                for s2 in range(4, 8):
                    if r(0x56 + s2) & 0x40 or r(0xCB + s2) >= 8:
                        if 8 <= r(0xCB + s2) < 0x10 and r(0xCB + s2) != k:
                            e.wr(0xCB + s2, k)
                # Alex "holds" the first weapon object in play (the object's
                # holder fields only; the game's own state for Alex is left alone)
                for s2 in range(4, 8):
                    if 8 <= r(0xCB + s2) < 0x10:
                        e.wr(0x56 + s2, r(0x56 + s2) | 0x40)
                        e.wr(0x3B7 + s2, 0)
                        break
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

    def set_pause(wanted, tag):
        # Poll state, not a lucky three-frame input offset. A hit animation can
        # defer pause eligibility; retain every failed attempt in the log.
        for attempt in range(4):
            e.held = {}
            step(12, tag + '-release')
            if bool(r(0x3F) & 0x20) == wanted:
                return True
            e.held = {START: 1}
            # Let the game's menu-entry/exit coroutine finish consuming the
            # press; $3F can change before that coroutine has reached its wait.
            step(12, tag)
            e.held = {}
            step(20, tag + '-settle')
            if bool(r(0x3F) & 0x20) == wanted:
                log(tag, 'accepted', 'attempt', attempt + 1)
                return True
            log(tag, 'not accepted', 'attempt', attempt + 1, 'state', r(0x4F))
        check(tag + ' accepted within bounded input window', False)
        return False

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
    for _ in range(8):
        if r(0x64C) == 3:
            break
        press(RIGHT, 6, 20, 'settings')
    check('S0 Gamer selected', r(0x64C) == 3)
    press(START, 12, 18, 'settings')
    for _ in range(60):
        if street():
            break
        press(A, 8, 12, 'story')
    menu_starts = S['starts']
    check('S0 reached the street', street(), f'mode={r(6):02x}')
    fight(1200, 'take', 'take')
    fight(3000, 'fight')
    # weapon phase (test only): every weapon object in play is re-kinded to one
    # weapon at a time, so goon hits / throws on Alex use each profile
    for k in sorted(KINDS):
        fight(1000, f'kind{k:02x}', f'kind{k:02x}')
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
        set_pause(True, 'pause')
        for i in range(90):
            step(1, 'pause')
            if r(0x3F) & 0x20:
                saw_pause += 1
                if i > 8 and (rr(TIMER) != 0 or rr(OFF) != 0 or rr(SENT) != 0):
                    pause_bad += 1
        e.png(f'R-paused-{k + 1}')
        set_pause(False, 'unpause')
        step(60, 'unpause-settle')
    # boss rule: goon classes forced to a boss class (test only). Fight until the
    # phase has produced BOSS pulses (or time runs out), so the result does not
    # depend on whether this trajectory happens to meet a boss.
    boss0 = S['events'].get('BOSS', 0)
    for _ in range(8):
        fight(750, 'boss', 'boss')
        if S['events'].get('BOSS', 0) - boss0 >= 3:
            break
    boss_phase = S['events'].get('BOSS', 0) - boss0
    set_pause(True, 'endpause')
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
    seen = {k.split('/')[1] for k in S['weapons']}
    log('weapon pulses', S['weapons'])
    check('S5 weapon profiles: pulses with several weapons, levels from the weapon table',
          len(seen) >= 4 and S['badLevel'] == 0, f'weapons={sorted(seen)}')
    ticks.close()
    (out / 'pulses.json').write_text(json.dumps(pulses, indent=1))
    log('DONE fails', len(fails), fails)
    return fails


if __name__ == '__main__':
    sys.exit(1 if main(sys.argv[1], sys.argv[2]) else 0)
