"""Street walk per difficulty: a spawn must never write another actor's stats.

Fighter stats live in 4-wide arrays, stat k of actor slot s at $049F+4k+s
(Alex is slot 0, $04BF is his stamina). Walking the street never changes
Alex's eight combat stats, so any change there is a spawn storing into the
wrong slot. Headless snes9x via tools.gamer_accept_snes9x.Emu.

usage: python3 -m tools.check_difficulty_slots ROM [SKILL ...] [--seconds N]
"""
import argparse
import json
from pathlib import Path

from tools.gamer_accept_snes9x import A, B, LEFT, RIGHT, START, Y, Emu

STATS = [0x49F + 4 * k for k in range(9)]


def run(rom, skill, seconds, out):
    e = Emu(rom, out)
    rd = e.rd

    def wait(pred, n):
        for _ in range(n):
            if pred():
                return True
            e.step()
        return pred()

    title = lambda: rd(6) == 0x3D and rd(0x100) == 0x80 and rd(0x1CA0) == 0
    settings = lambda: rd(6) == 5 and rd(0x1CA0) == 0
    street = lambda: (rd(0x100) & 0xC0) == 0xC0 and rd(6) != 5 and rd(0x1CA0) == 0
    if not wait(title, 2400):
        raise SystemExit('title not reached')
    e.press(START, 12, 18)
    if not wait(settings, 600):
        raise SystemExit('settings not reached')
    e.step(20)
    for _ in range(8):
        if rd(0x64C) == skill:
            break
        e.press(RIGHT, 6, 20)
    if rd(0x64C) != skill:
        raise SystemExit(f'skill {skill} not selectable (at {rd(0x64C)})')
    e.press(START, 3, 1)
    for _ in range(40):
        e.step(15)
    for _ in range(60):
        if street():
            break
        e.press(A, 8, 12)
    if not street():
        raise SystemExit('street not reached')
    e.step(30)

    def alex():
        return [rd(a) for a in STATS[:8]]

    base = alex()
    changes, spawned = [], set()
    for f in range(seconds * 60):
        sec = f // 60
        ph = (e.frame // 20) % 6
        e.held = {RIGHT: int(sec % 10 < 6), LEFT: int(sec % 10 >= 8), Y: int(ph == 1), B: int(ph == 3)}
        if rd(0x4BF) < 0x20:
            e.wr(0x4BF, 0x7F)     # keep Alex standing; stamina is not judged
        e.step()
        for s in range(2, 8):
            spawned.add(rd(0x4F5 + s))
        now = alex()
        if now != base:
            changes.append(dict(frame=e.frame, before=base, after=now,
                                classes=[rd(0x4F5 + s) for s in range(8)]))
            base = now
    return dict(rom=str(rom), skill=skill, seconds=seconds, alex_stat_changes=len(changes),
                first_changes=changes[:5], classes_seen=sorted(spawned), past_end_04C3=rd(0x4C3))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('rom')
    p.add_argument('skills', nargs='*', type=int, default=[1, 4, 2, 3])
    p.add_argument('--seconds', type=int, default=120)
    p.add_argument('--out', type=Path, default=Path('tmp/difficulty_slots'))
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    results = [run(a.rom, s, a.seconds, a.out) for s in a.skills]
    for r in results:
        print(json.dumps(r))
    raise SystemExit(1 if any(r['alex_stat_changes'] for r in results) else 0)


if __name__ == '__main__':
    main()
