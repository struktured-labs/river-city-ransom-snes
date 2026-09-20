"""Surgical compact-index plus paired-row trial, leaving all scheduling intact."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.benchmark_report import sha
from tools.build_hidden_index_trial import assemble as scalar_assemble, labels
from tools.build_inline_pitch_trial import checksum

HELPER = 0xD500
SIZE = 0x500


def assemble(out):
    subprocess.run(['.deps/cc65/bin/ca65', '-g', '-I', 'snes', '-o', str(out/'pair.o'),
                    'snes/compact_pair_reprobe.asm'], check=True)
    subprocess.run(['.deps/cc65/bin/ld65', '-C', 'snes/compact_pair_reprobe.cfg',
                    '-Ln', str(out/'pair.lbl'), '-o', str(out/'pair.bin'), str(out/'pair.o')], check=True)
    return (out/'pair.bin').read_bytes()


def patch(image, helper, original, entry):
    if len(image) != 0x200000 or len(helper) != SIZE or not 0x8000 < entry < HELPER:
        raise ValueError('Invalid cartridge/helper layout')
    if len(original) < 3 or image[entry:entry+len(original)] != original:
        raise ValueError('Original compact helper differs')
    if image[HELPER:HELPER+SIZE] != b'\xff'*SIZE or helper[:4] != original[:4]:
        raise ValueError('Occupied relocation space or wrong helper entry')
    result = bytearray(image)
    result[entry:entry+3] = b'\x4c'+HELPER.to_bytes(2, 'little')
    result[HELPER:HELPER+SIZE] = helper
    checksum(result)
    allowed = set(range(entry, entry+3)) | set(range(HELPER, HELPER+SIZE)) | set(range(0xFFDC, 0xFFE0))
    if any(i not in allowed for i, (a, b) in enumerate(zip(image, result)) if a != b):
        raise ValueError('Unrelated cartridge mutation')
    return bytes(result)


def build(parent, out):
    if out.exists():
        raise ValueError('Fresh output required')
    meta = json.loads((parent/'manifest.json').read_text())
    rom = parent/'native-cpu.sfc'
    if (sha(rom) != meta['rom_sha256'] or not meta['experimental_hidden_compact_index']
            or meta['experimental_hidden_direct_pair']):
        raise ValueError('Need authenticated scalar compact-index parent')
    compact = meta['hidden_compact_index']
    entry, end = compact['start'], compact['new_end']
    shutil.copytree(parent, out)
    scalar, symbols = scalar_assemble(out/'scalar-reprobe', entry, end-entry, True)
    if symbols['helper_end'] != end:
        raise ValueError('Scalar helper boundary changed')
    helper = assemble(out)
    result = patch(rom.read_bytes(), helper, scalar, entry)
    (out/'native-cpu.sfc').write_bytes(result)
    metadata = dict(helper=HELPER, size=SIZE, old_entry=entry,
        default_enabled=False, release_ready=False,
        sources={str(p): sha(p) for p in (Path(__file__), Path('snes/compact_pair_reprobe.asm'),
            Path('snes/compact_pair_reprobe.cfg'), Path('snes/hidden_direct_rows.inc'),
            Path('tools/build_hidden_index_trial.py'), Path('tools/build_inline_pitch_trial.py'),
            rom, parent/'manifest.json', out/'pair.bin', out/'pair.lbl')},
        scope='Exact old compact helper reassembled; its entry jumps to the existing guarded paired '
        'implementation combined with compact indexing. Old internal labels are retained for source '
        'history but no longer describe the active relocated helper; pair.lbl is authoritative. '
        'No budget, original timer, graphics, audio or interrupt policy changes.')
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'), experimental_compact_pair_reprobe=metadata)
    (out/'manifest.json').write_text(json.dumps(meta, indent=2)+'\n')
    print(json.dumps(dict(out=str(out), rom_sha256=meta['rom_sha256'],
                          helper_bytes=labels(out/'pair.lbl')['helper_end']-HELPER)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    build(**vars(p.parse_args()))
