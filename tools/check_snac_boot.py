"""Short ideal-pad guard; cannot certify physical SNAC timing."""
import hashlib
import json
from pathlib import Path
import sys
import time
from tools.gamer_accept_snes9x import Emu, B, START, RIGHT, A


def main(rom, output):
    t = time.monotonic()
    out = Path(output)
    out.mkdir(parents=True, exist_ok=False)
    e = Emu(rom, out)
    checks = []

    def check(name, ok):
        checks.append(dict(name=name, passed=bool(ok), frame=e.frame))
        print(checks[-1], flush=True)

    def wait(pred, limit):
        for _ in range(limit):
            if pred():
                return True
            e.step()
        return pred()

    title = lambda: e.rd(6) == 0x3D and e.rd(0x100) == 0x80 and e.rd(0x1CA0) == 0 and e.rd(0x1212F) == 0xCF and e.rd(0x12130) == 0xCB
    check('boot reaches title', wait(title, 2400))
    e.press(B, 12, 30)
    check('B does not act as Start', title())
    e.press(START, 12, 30)
    check('Start opens settings', wait(lambda: e.rd(6) == 5 and e.rd(0x1CA0) == 0, 600))
    e.step(180)  # mode 5 precedes the interactive settings screen
    before = e.rd(0x64C)
    e.press(RIGHT, 12, 30)
    check('Right changes skill selection', e.rd(0x64C) != before)
    e.press(START, 12, 30)
    for _ in range(40):
        if e.rd(0x100) & 0xC0 == 0xC0 and e.rd(6) != 5 and e.rd(0x1CA0) == 0:
            break
        e.press(A, 8, 12)  # dismiss the original story text
    check('Start enters gameplay', wait(lambda: e.rd(0x100) & 0xC0 == 0xC0 and e.rd(6) != 5 and e.rd(0x1CA0) == 0, 600))
    e.step(120)
    e.png('gameplay')
    report = dict(rom=str(rom), sha256=hashlib.sha256(Path(rom).read_bytes()).hexdigest(),
                  core_sha256=hashlib.sha256(Path('.deps/snes9x/libretro/snes9x_libretro.so').read_bytes()).hexdigest(),
                  checks=checks, seconds=time.monotonic()-t, hardware_verified=False,
                  scope=__doc__)
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    return 0 if all(c['passed'] for c in checks) else 1


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:]))
