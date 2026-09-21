"""Smooth log pitch drop into slower 55 Hz wubs. Splash ident only."""
import argparse
import json
import math
from pathlib import Path
import shutil

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_sub_wub_trial import curve as parent_curve

DESCENT = 150
START_HZ = 311
END_HZ = 55
TAIL_PERIOD = 40
PEAK = 118
MASTER = bytes.fromhex('8f70f3')
MASTER_LOUD = bytes.fromhex('8f7ff3')
MASTER_SMOOTH = bytes.fromhex('8f78f3')


def stepped_curve():
    """4146/4166 stair-step ident, kept so we can find it in a parent ROM."""
    data = bytearray()
    for frame in range(240):
        if frame < 150:
            step, phase = divmod(frame, 5)
            hz = START_HZ * 2 ** (-30 * step / 29 / 12)
            wobble = 0.72 + 0.28 * math.cos(2 * math.pi * phase / 5)
            volume = round(127 * wobble)
        else:
            hz = END_HZ
            t = frame - 150
            pulse = (0.5 + 0.5 * math.cos(2 * math.pi * t / TAIL_PERIOD)) ** 1.6
            volume = 0 if t >= 85 else round(127 * (0.22 + 0.78 * pulse))
        pitch = max(1, min(0x3fff, round(hz * 4096 / 1000)))
        data.extend((pitch & 255, pitch >> 8, volume))
    return bytes(data)


def curve():
    data = bytearray()
    for frame in range(240):
        if frame < DESCENT:
            t = frame / (DESCENT - 1)
            hz = START_HZ * (END_HZ / START_HZ) ** t
            attack = min(1.0, (frame + 1) / 6)
            wobble = 0.90 + 0.10 * math.cos(2 * math.pi * frame / 18)
            volume = round(PEAK * attack * wobble)
        else:
            hz = END_HZ
            t = frame - DESCENT
            pulse = (0.5 + 0.5 * math.cos(2 * math.pi * t / TAIL_PERIOD)) ** 1.4
            fade = 1.0 if t < 55 else max(0.0, 1.0 - (t - 55) / 35)
            volume = round(PEAK * (0.30 + 0.70 * pulse) * fade)
        pitch = max(1, min(0x3fff, round(hz * 4096 / 1000)))
        data.extend((pitch & 255, pitch >> 8, min(127, volume)))
    return bytes(data)


def _find_table(image):
    spc = image[0x110000:0x120000]
    for old in (stepped_curve(), parent_curve()):
        if spc.count(old) == 1:
            return 0x110000 + spc.find(old)
    raise ValueError('Expected unique ident table')


def patch(image):
    if len(image) != 0x200000:
        raise ValueError('Need a 2 MiB native image')
    offset = _find_table(image)
    result = bytearray(image)
    result[offset:offset + 720] = curve()
    spc = result[0x110000:0x120000]
    allowed = set(range(offset, offset + 720)) | set(range(0xffdc, 0xffe0))
    for old in (MASTER, MASTER_LOUD):
        at = 0
        while True:
            found = spc.find(old, at)
            if found < 0:
                break
            abs_at = 0x110000 + found
            result[abs_at:abs_at + 3] = MASTER_SMOOTH
            allowed.update(range(abs_at, abs_at + 3))
            at = found + 3
    checksum(result)
    if any(i not in allowed for i, (a, b) in enumerate(zip(image, result)) if a != b):
        raise ValueError('Edit outside ident table/master/checksum')
    return bytes(result), offset


def build(parent, out):
    meta = json.loads((parent / 'manifest.json').read_text())
    rom = parent / 'native-cpu.sfc'
    if out.exists() or sha(rom) != meta['rom_sha256']:
        raise ValueError('Fresh output and bound parent ROM required')
    changed, offset = patch(rom.read_bytes())
    out.mkdir(parents=True)
    for source in parent.iterdir():
        if source.is_file():
            shutil.copy2(source, out / source.name)
    (out / 'native-cpu.sfc').write_bytes(changed)
    (out / 'splash-ident-curve.bin').write_bytes(curve())
    (out / 'splash.bin').write_bytes(changed[0x110000:0x120000])
    spc_src = parent / 'splash-ident-spc.bin'
    if not spc_src.exists():
        spc_src = Path('build/chromatic-wub-game-4146/splash-ident-spc.bin')
    old_spc = spc_src.read_bytes()
    if len(old_spc) != 585 or changed[0x110000:0x120000].count(old_spc[:8]) != 1:
        raise ValueError('Ident SPC payload moved')
    spc_at = 0x110000 + changed[0x110000:0x120000].index(old_spc[:8])
    (out / 'splash-ident-spc.bin').write_bytes(changed[spc_at:spc_at + 585])
    meta['rom_sha256'] = sha(out / 'native-cpu.sfc')
    meta['splash']['ident_curve_sha256'] = sha(out / 'splash-ident-curve.bin')
    meta['splash']['ident_spc_sha256'] = sha(out / 'splash-ident-spc.bin')
    meta['splash']['chromatic_wub_trial'] = dict(
        parent=str(parent), table_offset=offset, start_hz=START_HZ, end_hz=END_HZ,
        descent_frames=DESCENT, tail_period_frames=TAIL_PERIOD, peak_volume=PEAK,
        master=0x78, smooth_log_slide=True, physical_verified=False, release_ready=False,
        scope=__doc__, sources={str(p): sha(p) for p in (
            Path(__file__), Path('tools/build_sub_wub_trial.py'),
            Path('tools/build_inline_pitch_trial.py'), parent / 'manifest.json', rom,
            parent / 'manifest.json', rom)})
    (out / 'manifest.json').write_text(json.dumps(meta, indent=2) + '\n')
    print(json.dumps(dict(out=str(out), rom_sha256=meta['rom_sha256'], table_offset=offset)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    build(**vars(p.parse_args()))
