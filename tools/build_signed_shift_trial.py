"""In-place, default-off equivalent signed >>5 loop; no timing/fade changes."""
import argparse
import json
from pathlib import Path
import shutil

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

ADDRESS = 0xC3B9
ORIGINAL = bytes.fromhex('a205a98025274627052785276626cad0f1')
# LDX #5; loop: LDA $27 / CMP #$80 / ROR $27 / ROR $26 / DEX / BNE loop;
# restore original final A and DEX's N=0,Z=1 without changing final carry.
OPTIMIZED = bytes.fromhex('a205a527c98066276626cad0f5a527a200')


def patch(image):
    result = bytearray(image)
    if len(ORIGINAL) != len(OPTIMIZED):
        raise ValueError('In-place loop length changed')
    for bank in range(1, 9):
        offset = bank*65536+ADDRESS
        if result[offset:offset+len(ORIGINAL)] != ORIGINAL:
            raise ValueError(f'Unexpected original signed shift in bank {bank}')
        result[offset:offset+len(ORIGINAL)] = OPTIMIZED
    checksum(result)
    return bytes(result)


def build(parent, out):
    manifest = json.loads((parent/'manifest.json').read_text())
    rom = parent/'native-cpu.sfc'
    if sha(rom) != manifest['rom_sha256']:
        raise ValueError('Changed parent cartridge')
    changed = patch(rom.read_bytes())
    shutil.copytree(parent, out)
    (out/'native-cpu.sfc').write_bytes(changed)
    manifest.update(rom_sha256=sha(out/'native-cpu.sfc'), experimental_signed_shift=dict(
        default_enabled=False, address=ADDRESS, banks=list(range(1, 9)),
        before=ORIGINAL.hex(), after=OPTIMIZED.hex(),
        sources={str(p):sha(p) for p in (Path(__file__),
            Path('tools/build_inline_pitch_trial.py'), parent/'manifest.json', rom)},
        scope='Same signed shift, final A/X/Y/P and operand bytes. Shorter execution, '
              'not instruction-by-instruction interrupt equivalence or release qualification.'))
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(dict(out=str(out), rom_sha256=manifest['rom_sha256'])))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    build(**vars(p.parse_args()))
