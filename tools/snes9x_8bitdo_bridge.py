"""Map 8BitDo Ultimate 2 (xpad / event gamepad) onto Snes9x's existing keyboard binds.

Ignores the pad's extra Keyboard/Mouse HID interfaces. Ultimate 2 Xbox labels:
south A = punch (SNES B), east B = jump (SNES A).
"""
from __future__ import annotations

import sys
import time

from evdev import InputDevice, UInput, ecodes, list_devices

# Ultimate 2 Xbox labels. Port: SNES B = punch, SNES A = jump.
KEYS = {
    ecodes.BTN_SOUTH: ecodes.KEY_Z,
    ecodes.BTN_EAST: ecodes.KEY_X,
    ecodes.BTN_WEST: ecodes.KEY_S,
    ecodes.BTN_NORTH: ecodes.KEY_A,
    ecodes.BTN_TL: ecodes.KEY_Q,
    ecodes.BTN_TR: ecodes.KEY_W,
    ecodes.BTN_SELECT: ecodes.KEY_TAB,
    ecodes.BTN_START: ecodes.KEY_ENTER,
}
STICK = {
    ecodes.ABS_X: (ecodes.KEY_LEFT, ecodes.KEY_RIGHT),
    ecodes.ABS_Y: (ecodes.KEY_UP, ecodes.KEY_DOWN),
    ecodes.ABS_HAT0X: (ecodes.KEY_LEFT, ecodes.KEY_RIGHT),
    ecodes.ABS_HAT0Y: (ecodes.KEY_UP, ecodes.KEY_DOWN),
}
SKIP = ('keyboard', 'mouse', 'consumer', 'snes9x')
CAP = {ecodes.EV_KEY: [
    ecodes.KEY_X, ecodes.KEY_Z, ecodes.KEY_S, ecodes.KEY_A, ecodes.KEY_Q, ecodes.KEY_W,
    ecodes.KEY_TAB, ecodes.KEY_ENTER, ecodes.KEY_LEFT, ecodes.KEY_RIGHT,
    ecodes.KEY_UP, ecodes.KEY_DOWN,
]}


def is_pad(dev: InputDevice) -> bool:
    name = (dev.name or '').lower()
    if any(tok in name for tok in SKIP):
        return False
    keys = set(dev.capabilities().get(ecodes.EV_KEY, []))
    return bool(keys & {ecodes.BTN_SOUTH, ecodes.BTN_GAMEPAD})


def find_pad() -> InputDevice | None:
    found = []
    for path in list_devices():
        try:
            dev = InputDevice(path)
        except OSError:
            continue
        if is_pad(dev):
            found.append(dev)
    if not found:
        return None
    found.sort(key=lambda d: (0 if '8bitdo' in (d.name or '').lower() else 1, d.path))
    return found[0]


def emit(ui: UInput, key: int, value: int, held: dict[int, int]) -> None:
    if held.get(key) == value:
        return
    held[key] = value
    ui.write(ecodes.EV_KEY, key, value)
    ui.syn()


def run(dev: InputDevice) -> None:
    ui = UInput(CAP, name='RCR 8BitDo → Snes9x')
    held: dict[int, int] = {}
    print(f'DONE pad={dev.path} name={dev.name!r}', flush=True)
    try:
        for event in dev.read_loop():
            if event.type == ecodes.EV_KEY:
                key = KEYS.get(event.code)
                if key is not None and event.value in (0, 1):
                    emit(ui, key, event.value, held)
            elif event.type == ecodes.EV_ABS:
                if event.code not in STICK:
                    continue
                neg, pos = STICK[event.code]
                if event.code in (ecodes.ABS_HAT0X, ecodes.ABS_HAT0Y):
                    emit(ui, neg, 1 if event.value < 0 else 0, held)
                    emit(ui, pos, 1 if event.value > 0 else 0, held)
                    continue
                info = dev.absinfo(event.code)
                mid = (info.max + info.min) / 2
                dead = max(8000, (info.max - info.min) * 0.25)
                delta = event.value - mid
                emit(ui, neg, 1 if delta < -dead else 0, held)
                emit(ui, pos, 1 if delta > dead else 0, held)
    finally:
        ui.close()


def main() -> int:
    timeout = float(sys.argv[1]) if len(sys.argv) > 1 else 0
    deadline = time.time() + timeout if timeout > 0 else None
    while True:
        pad = find_pad()
        if pad is not None:
            try:
                run(pad)
            except OSError as exc:
                print(f'dropped pad errno={exc.errno} — waiting for Ultimate 2 XInput', flush=True)
                time.sleep(0.5)
                continue
            if timeout > 0:
                return 0
            continue
        if deadline is not None and time.time() >= deadline:
            print('FAILED no 8BitDo gamepad in evdev', flush=True)
            return 1
        time.sleep(0.5)


if __name__ == '__main__':
    raise SystemExit(main())
