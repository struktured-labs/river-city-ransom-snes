"""Offline splash-only trial: open/close the overtone over the fixed bass tail.

Keep the existing 55 Hz, three-pulse automation and exact SPC payload size.
This is harmonic amplitude shaping, not a resonant filter or a new game engine.
"""
import argparse
import json
from pathlib import Path
import shutil

from tools.benchmark_report import sha
from tools.build_ident_spc import build as ident, LOAD
from tools.build_inline_pitch_trial import checksum
from tools.build_sub_wub_trial import curve

HELPER = 0x1B0  # payload offset; SPC address $03B0, before directory $0400
CALLSITE = bytes.fromhex('5c c4 f3')  # half-volume then DSP write


def helper():
    # Entry: A = sub volume, DSP address = voice1 left volume.
    # Preserve Y and leave A = overtone volume for caller's right write.
    # Before note144 keep original floor(volume/2). During the tail use
    # 2*floor(volume**2/256), making harmonic/sub ratio open with the pulse.
    # Count09 increments after the volume write, so it is this note's index.
    return bytes.fromhex(
        '2d e4 09 68 90 90 0b'  # PUSH A; MOV A,$09; CMP #144; BCC old
        'ae 6d fd cf dd 1c ee c4 f3 6f'  # POP A; PUSH Y; Y=A; MUL; A=Y; ASL; POP Y; write; RET
        '00'  # unreachable padding: keeps the branch landing explicit
        'ae 5c c4 f3 6f')  # old: POP A; LSR A; write; RET


def payload():
    old = ident()
    if old.count(CALLSITE) != 1 or any(old[HELPER:512]):
        raise ValueError('Ident code/preimage or free padding changed')
    code = helper()
    if HELPER + len(code) > 512:
        raise ValueError('Helper overlaps directory')
    data = bytearray(old)
    call = old.index(CALLSITE)
    data[call:call+3] = b'\x3f' + (LOAD+HELPER).to_bytes(2, 'little')
    data[HELPER:HELPER+len(code)] = code
    return bytes(data)


def patch(image):
    old, new = ident(), payload()
    if len(image) != 0x200000 or image[0x110000:0x120000].count(old) != 1:
        raise ValueError('Expected unique stock ident in splash bank')
    offset = image.index(old, 0x110000, 0x120000)
    result = bytearray(image)
    result[offset:offset+len(old)] = new
    checksum(result)
    allowed = set(range(offset, offset+len(old))) | set(range(0xffdc, 0xffe0))
    if any(i not in allowed for i,(a,b) in enumerate(zip(image,result)) if a != b):
        raise ValueError('Unrelated cartridge edit')
    return bytes(result), offset


def build(parent, out):
    meta = json.loads((parent/'manifest.json').read_text())
    rom = parent/'native-cpu.sfc'
    if (out.exists() or sha(rom) != meta['rom_sha256'] or
            (parent/'splash-ident-spc.bin').read_bytes() != ident() or
            sha(parent/'splash-ident-spc.bin') != meta['splash']['ident_spc_sha256'] or
            (parent/'splash-ident-curve.bin').read_bytes() != curve() or
            sha(parent/'splash-ident-curve.bin') != meta['splash']['ident_curve_sha256']):
        raise ValueError('Fresh output and bound current 55 Hz parent required')
    changed, offset = patch(rom.read_bytes())
    out.mkdir(parents=True)
    for source in parent.iterdir():
        if source.is_file():
            shutil.copy2(source, out/source.name)
    (out/'native-cpu.sfc').write_bytes(changed)
    (out/'splash.bin').write_bytes(changed[0x110000:0x120000])
    (out/'splash-ident-spc.bin').write_bytes(payload())
    meta['rom_sha256'] = sha(out/'native-cpu.sfc')
    meta['splash']['ident_spc_sha256'] = sha(out/'splash-ident-spc.bin')
    meta['splash']['harmonic_wub_trial'] = dict(parent=str(parent), spc_offset=offset,
        fixed_pitch_hz=55, nominal_pulse_period_frames=30,
        direct_silence_from=219, physical_verified=False, release_ready=False,
        scope=__doc__, sources={str(p):sha(p) for p in (
            Path(__file__), Path('tools/build_ident_spc.py'),
            Path('tools/build_sub_wub_trial.py'), Path('tools/build_inline_pitch_trial.py'),
            parent/'manifest.json', rom, parent/'splash-ident-spc.bin',
            parent/'splash-ident-curve.bin')})
    (out/'manifest.json').write_text(json.dumps(meta, indent=2)+'\n')
    print(json.dumps(dict(out=str(out), rom_sha256=meta['rom_sha256'])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    build(**vars(p.parse_args()))
