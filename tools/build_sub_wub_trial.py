"""Splash-only 55 Hz landing; three slow pulses, then existing echo drains.

No new synth, game audio engine, graphics, or CPU timing changes. The earlier
110 Hz tail remains an audition control; this is a separate opt-in candidate.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_wub_tail_trial import curve as parent_curve


def curve():
    result = bytearray(parent_curve())
    for frame in range(240):
        # Continuous exponential slide, then a stationary A1 sub-bass note.
        hz = 311 * (55 / 311) ** (min(frame, 144) / 144)
        pitch = round(hz * 4096 / 1000)
        result[frame*3:frame*3+2] = pitch.to_bytes(2, 'little')
        if 114 <= frame < 144:
            # Ease out of the slide before opening the first slow pulse.
            # Without this dip, its echo smears the first tail peak later.
            pulse = (.5+.5*math.cos(2*math.pi*(frame-114)/30))**1.4
            result[frame*3+2] = round(116*(.06+.94*pulse))
    return bytes(result)


def patch(image):
    old, new = parent_curve(), curve()
    if len(image) != 0x200000 or image[0x110000:0x120000].count(old) != 1:
        raise ValueError('Expected unique prior slow-wub table in exact HiROM')
    offset = image.index(old, 0x110000, 0x120000)
    result = bytearray(image)
    result[offset:offset+720] = new
    checksum(result)
    allowed = {offset+3*i+j for i in range(240) for j in (0, 1)} | {offset+3*i+2 for i in range(114,144)} | set(range(0xffdc, 0xffe0))
    if any(i not in allowed for i, (a,b) in enumerate(zip(image,result)) if a != b):
        raise ValueError('Edit outside pitch/transition table/checksum')
    return bytes(result), offset


def build(parent, out):
    meta = json.loads((parent/'manifest.json').read_text())
    rom = parent/'native-cpu.sfc'
    if (out.exists() or sha(rom) != meta['rom_sha256'] or
            (parent/'splash-ident-curve.bin').read_bytes() != parent_curve() or
            meta['splash']['ident_curve_sha256'] != sha(parent/'splash-ident-curve.bin')):
        raise ValueError('Fresh output and hash-bound prior wub required')
    changed, offset = patch(rom.read_bytes())
    out.mkdir(parents=True)
    for source in parent.iterdir():
        if source.is_file():
            shutil.copy2(source, out/source.name)
    (out/'native-cpu.sfc').write_bytes(changed)
    (out/'splash.bin').write_bytes(changed[0x110000:0x120000])
    (out/'splash-ident-curve.bin').write_bytes(curve())
    meta['rom_sha256'] = sha(out/'native-cpu.sfc')
    meta['splash']['ident_curve_sha256'] = hashlib.sha256(curve()).hexdigest()
    meta['splash']['sub_wub_trial'] = dict(parent=str(parent), table_offset=offset,
        fixed_pitch_hz=55, pulse_period_frames=30, peak_frames=[144,174,204],
        direct_silence_from=219, release_ready=False,
        sources={str(p):sha(p) for p in (Path(__file__), Path('tools/build_wub_tail_trial.py'),
            Path('tools/build_inline_pitch_trial.py'), Path('tools/build_ident_spc.py'),
            parent/'manifest.json', rom, parent/'splash-ident-curve.bin')})
    (out/'manifest.json').write_text(json.dumps(meta, indent=2)+'\n')
    print(json.dumps(dict(out=str(out), rom_sha256=meta['rom_sha256'])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    build(**vars(p.parse_args()))
