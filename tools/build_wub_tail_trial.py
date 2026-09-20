"""Change only ident automation: unchanged descent, fixed low pitch, three slow wubs."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_ident_spc import curve as original_curve


def curve():
    data = bytearray(original_curve())
    for frame in range(144, 240):
        t = frame-144
        # Peaks at144,174,204: ~2Hz instead of the old shallow3Hz modulation.
        # Stop driving at219; remaining21 frames let the existing echo decay.
        pulse = (.5+.5*math.cos(2*math.pi*t/30))**1.4
        volume = round(116*(.06+.94*pulse)) if t < 75 else 0
        pitch = round(110*4096/1000)
        data[frame*3:frame*3+3] = bytes((pitch & 255, pitch >> 8, volume))
    return bytes(data)


def patch(image, old, new):
    if len(image) != 0x200000 or len(old) != 720 or len(new) != 720 or new[:432] != old[:432]:
        raise ValueError('Need exact240-frame table with unchanged descent')
    bank = image[0x110000:0x120000]
    if bank.count(old) != 1:
        raise ValueError('Missing/ambiguous original ident table')
    offset = 0x110000+bank.index(old)
    result = bytearray(image)
    result[offset:offset+720] = new
    checksum(result)
    allowed = set(range(offset+432, offset+720)) | set(range(0xffdc, 0xffe0))
    if any(i not in allowed for i, (a, b) in enumerate(zip(image, result)) if a != b):
        raise ValueError('Unrelated cartridge edit')
    return bytes(result), offset


def build(parent, out):
    m = json.loads((parent/'manifest.json').read_text())
    rom = parent/'native-cpu.sfc'
    old, new = original_curve(), curve()
    if (sha(rom) != m['rom_sha256'] or m['splash']['hold_frames'] != 240 or
            m['splash']['ident_curve_sha256'] != hashlib.sha256(old).hexdigest() or
            (parent/'splash-ident-curve.bin').read_bytes() != old):
        raise ValueError('Different parent ident')
    changed, offset = patch(rom.read_bytes(), old, new)
    shutil.copytree(parent, out)
    (out/'native-cpu.sfc').write_bytes(changed)
    (out/'splash-ident-curve.bin').write_bytes(new)
    # Keep this derived splash binary consistent; graphics/code/SPC unchanged.
    (out/'splash.bin').write_bytes(changed[0x110000:0x120000])
    m['rom_sha256'] = sha(out/'native-cpu.sfc')
    m['splash']['ident_curve_sha256'] = sha(out/'splash-ident-curve.bin')
    m['splash']['wub_tail_trial'] = dict(parent_rom_sha256=sha(rom), table_offset=offset,
        fixed_pitch_hz=110, pulse_period_frames=30, peak_frames=[144, 174, 204],
        direct_silence_from=219, release_ready=False, scope=__doc__,
        sources={str(p): sha(p) for p in (Path(__file__), Path('tools/build_ident_spc.py'),
            Path('tools/build_inline_pitch_trial.py'), parent/'manifest.json', rom,
            parent/'splash-ident-curve.bin')})
    (out/'manifest.json').write_text(json.dumps(m, indent=2)+'\n')
    print(json.dumps(dict(out=str(out), rom_sha256=m['rom_sha256'], table_offset=offset)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    build(**vars(p.parse_args()))
