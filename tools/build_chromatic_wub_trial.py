"""Louder chromatic dubstep descent, then slower 55 Hz cadenced wubs.

Splash ident only. Same 240-frame table size. No game-audio engine change.
"""
import argparse
import json
import math
from pathlib import Path
import shutil

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_sub_wub_trial import curve as parent_curve

STEP_LEN = 5
STEPS = 30
DESCENT = STEP_LEN * STEPS
START_HZ = 311
END_HZ = 55
TAIL_PERIOD = 40
MASTER = bytes.fromhex('8f70f3')
MASTER_LOUD = bytes.fromhex('8f7ff3')


def curve():
    data = bytearray()
    for frame in range(240):
        if frame < DESCENT:
            step, phase = divmod(frame, STEP_LEN)
            hz = START_HZ * 2 ** (-30 * step / 29 / 12)
            wobble = 0.72 + 0.28 * math.cos(2 * math.pi * phase / STEP_LEN)
            volume = round(127 * wobble)
        else:
            hz = END_HZ
            t = frame - DESCENT
            pulse = (0.5 + 0.5 * math.cos(2 * math.pi * t / TAIL_PERIOD)) ** 1.6
            volume = 0 if t >= 85 else round(127 * (0.22 + 0.78 * pulse))
        pitch = max(1, min(0x3fff, round(hz * 4096 / 1000)))
        data.extend((pitch & 255, pitch >> 8, volume))
    return bytes(data)


def patch(image):
    old, new = parent_curve(), curve()
    if len(image) != 0x200000 or image[0x110000:0x120000].count(old) != 1:
        raise ValueError('Expected unique current 55 Hz ident table')
    offset = image.index(old, 0x110000, 0x120000)
    result = bytearray(image)
    result[offset:offset + 720] = new
    spc = result[0x110000:0x120000]
    if spc.count(MASTER) != 2:
        raise ValueError('Expected two ident master-volume writes')
    first = 0x110000 + spc.find(MASTER)
    second = 0x110000 + spc.find(MASTER, first - 0x110000 + 3)
    result[first:first + 3] = MASTER_LOUD
    result[second:second + 3] = MASTER_LOUD
    checksum(result)
    allowed = set(range(offset, offset + 720)) | set(range(first, first + 3)) | set(range(second, second + 3)) | set(range(0xffdc, 0xffe0))
    if any(i not in allowed for i, (a, b) in enumerate(zip(image, result)) if a != b):
        raise ValueError('Edit outside ident table/master/checksum')
    return bytes(result), offset


def build(parent, out):
    meta = json.loads((parent / 'manifest.json').read_text())
    rom = parent / 'native-cpu.sfc'
    if (out.exists() or sha(rom) != meta['rom_sha256'] or
            (parent / 'splash-ident-curve.bin').read_bytes() != parent_curve() or
            sha(parent / 'splash-ident-curve.bin') != meta['splash']['ident_curve_sha256']):
        raise ValueError('Fresh output and bound 4108-line ident required')
    changed, offset = patch(rom.read_bytes())
    out.mkdir(parents=True)
    for source in parent.iterdir():
        if source.is_file():
            shutil.copy2(source, out / source.name)
    (out / 'native-cpu.sfc').write_bytes(changed)
    (out / 'splash-ident-curve.bin').write_bytes(curve())
    (out / 'splash.bin').write_bytes(changed[0x110000:0x120000])
    old_spc = (parent / 'splash-ident-spc.bin').read_bytes()
    if len(old_spc) != 585 or changed[0x110000:0x120000].count(old_spc[:8]) != 1:
        raise ValueError('Ident SPC payload moved')
    spc_at = 0x110000 + changed[0x110000:0x120000].index(old_spc[:8])
    (out / 'splash-ident-spc.bin').write_bytes(changed[spc_at:spc_at + 585])
    meta['rom_sha256'] = sha(out / 'native-cpu.sfc')
    meta['splash']['ident_curve_sha256'] = sha(out / 'splash-ident-curve.bin')
    meta['splash']['ident_spc_sha256'] = sha(out / 'splash-ident-spc.bin')
    meta['splash']['chromatic_wub_trial'] = dict(
        parent=str(parent), table_offset=offset, start_hz=START_HZ, end_hz=END_HZ,
        chromatic_steps=STEPS, step_frames=STEP_LEN, tail_period_frames=TAIL_PERIOD,
        peak_volume=127, master=0x7F, physical_verified=False, release_ready=False,
        scope=__doc__, sources={str(p): sha(p) for p in (
            Path(__file__), Path('tools/build_sub_wub_trial.py'),
            Path('tools/build_inline_pitch_trial.py'), parent / 'manifest.json', rom,
            parent / 'splash-ident-curve.bin', parent / 'splash-ident-spc.bin')})
    (out / 'manifest.json').write_text(json.dumps(meta, indent=2) + '\n')
    print(json.dumps(dict(out=str(out), rom_sha256=meta['rom_sha256'], table_offset=offset)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    build(**vars(p.parse_args()))
