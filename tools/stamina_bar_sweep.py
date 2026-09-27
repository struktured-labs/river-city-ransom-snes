"""Stamina HUD bar sweep: every stamina value 0-255, screenshots and ticks.

Boots to the street by ordinary input (settings Right to pick the skill),
then holds Alex's stamina ($04BF) at each value for HOLD frames by RAM poke
and reads the bar from the screen: 8 cells of 2 ticks, 4 px per tick, so
ticks = (green span + 3) / 4. Each value's HUD strip goes on a contact
sheet; key values are also saved whole.

Expected (see snes/stamina_bar.asm):
  Gamer ($064C=3):  ticks = ceil(stamina / 16) -> 0 only at 0, 16 only >= 241
  other skills:     the original NES bar, min(16, ceil(stamina / 8)) with the
                    8-bit (stamina + 7) wrap, measured on the NES ROM too
                    with --system nes (fceumm) so the SNES bar is compared
                    against the original, not against a formula alone.

usage: python3 -m tools.stamina_bar_sweep --system snes|nes --rom ROM --skill 1|3 --out DIR
"""
import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from tools import gamer_accept_snes9x as ga

CORES = {'snes': Path('.deps/snes9x/libretro/snes9x_libretro.so'),
         'nes': Path('.deps/fceumm/fceumm_libretro.so')}
HOLD = 48
RETRIES = 3
KEY = (0, 1, 8, 9, 16, 17, 63, 64, 120, 121, 127, 128, 200, 240, 241, 248, 249, 255)


def gamer_ticks(s):
    return 0 if s == 0 else (s - 1) // 16 + 1


def nes_ticks(s):
    return min(16, ((s + 7) & 0xFF) // 8)


def expected(skill, s):
    return gamer_ticks(s) if skill == 3 else nes_ticks(s)


def bar_ticks(img, top, bottom):
    xs = [x for x in range(40, 160) for y in range(top, bottom)
          if (lambda p: p[1] > 120 and p[2] < 100 and p[1] > p[0] + 30)(img.getpixel((x, y)))]
    return 0 if not xs else (max(xs) - min(xs) + 1 + 3) // 4, xs


def main(system, rom, skill, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    ga.CORE = CORES[system]
    e = ga.Emu(rom, out)
    r = e.rd
    street = lambda: (r(0x100) & 0xC0) == 0xC0 and r(6) != 5 and (system == 'nes' or r(0x1CA0) == 0)
    title = lambda: r(6) == 0x3D and r(0x100) == 0x80
    for _ in range(2400):
        if title():
            break
        e.step()
    if not title():
        raise SystemExit('never reached the title')
    e.press(ga.START, 12, 18)
    for _ in range(600):
        if r(6) == 5:
            break
        e.step()
    if r(6) != 5:
        raise SystemExit('never reached settings')
    e.step(60)
    if system == 'snes':
        for _ in range(8):
            if r(0x64C) == skill:
                break
            e.press(ga.RIGHT, 6, 20)
    if r(0x64C) != skill:
        raise SystemExit(f'skill {r(0x64C)} != {skill}')
    e.press(ga.START, 12, 18)
    for _ in range(80):
        if street():
            break
        e.press(ga.A, 8, 12)
    if not street():
        raise SystemExit('never reached the street')
    e.step(240)
    h = 224 if system == 'snes' else 240
    top, bottom = (0, 48) if system == 'snes' else (0, 56)
    rows, strips, fails = [], [], []
    for s in range(256):
        want = expected(skill, s)
        # A room scroll or a knockdown can delay the HUD redraw; hold longer
        # (up to RETRIES more windows) before calling a value wrong.
        for attempt in range(1 + RETRIES):
            seen = []
            for f in range(HOLD):
                e.wr(0x4BF, s)
                e.step()
                if f >= HOLD - 8:
                    img, _ = e.png('_frame')
                    seen.append(bar_ticks(img, top, bottom)[0])
            ticks = seen[-1]
            stable = len(set(seen)) == 1
            if stable and ticks == want:
                break
        rows.append(dict(stamina=s, ticks=ticks, expected=want, stable=stable, windows=attempt + 1))
        strips.append(img.crop((0, top, 256, bottom)))
        if s in KEY:
            img.save(out / f'stam-{s:03d}.png')
        if ticks != want or not stable:
            fails.append(s)
    (out / '_frame.png').unlink(missing_ok=True)
    # contact sheet: 256 strips, 8 columns
    sw, sh = 256, bottom - top
    sheet = Image.new('RGB', (8 * (sw + 40), 32 * sh), 'black')
    d = ImageDraw.Draw(sheet)
    for s, strip in enumerate(strips):
        x, y = (s % 8) * (sw + 40), (s // 8) * sh
        sheet.paste(strip, (x + 40, y))
        d.text((x + 2, y + sh // 2 - 5), str(s), fill='white')
    sheet.save(out / 'sweep-sheet.png')
    ticks = [row['ticks'] for row in rows]
    summary = dict(system=system, rom=str(rom), skill=skill, hold=HOLD,
                   monotonic=all(a <= b for a, b in zip(ticks, ticks[1:])),
                   empty_values=[s for s, t in enumerate(ticks) if t == 0],
                   full_from=next((s for s, t in enumerate(ticks) if t == 16), None),
                   mismatches=fails, rows=rows)
    (out / 'sweep.json').write_text(json.dumps(summary, indent=1) + '\n')
    print(json.dumps({k: v for k, v in summary.items() if k != 'rows'}))
    return fails


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--system', choices=CORES, default='snes')
    p.add_argument('--rom', required=True)
    p.add_argument('--skill', type=int, choices=(1, 2, 3, 4), default=3)
    p.add_argument('--out', required=True)
    a = p.parse_args()
    sys.exit(1 if main(a.system, a.rom, a.skill, a.out) else 0)
