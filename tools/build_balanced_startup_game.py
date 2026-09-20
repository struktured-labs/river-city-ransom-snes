"""Compact staging with the original no-restart flush cost preserved."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from tools.benchmark_report import sha
from tools.build_compact_startup_pitch import patch as compact_patch, FINISH, FLUSH, VALID, relative
from tools.build_inline_pitch_trial import checksum


def balance(compact):
    data = bytearray(compact)
    first = FINISH-0x400
    old = bytes((0xe8, 0, 0xc5, VALID & 255, VALID >> 8, 0xc4, 0x54, 0x8f, 0x7d, 0xf4, 0x6f, 0))
    new = bytes((0xe8, 0, 0xc5, VALID & 255, VALID >> 8, 0x8f, 0, 0x54, 0x8f, 0x7d, 0xf4, 0x6f))
    if data[first:first+12] != old:
        raise ValueError('Changed compact finish/free byte')
    branch = FLUSH-0x400+3
    if data[branch-3:branch] != bytes.fromhex('e454f0') or data[branch] != relative(FLUSH, 2, FINISH):
        raise ValueError('Changed zero-mask branch')
    # No stage helper stores validity unless its bit in$54 is set. A completed
    # pending flush clears validity, and IPL upload initializes it to zero.
    # Therefore mask0 does not need another validity clear. Enter the exact old
    # MOV$54,#0; MOV$F4,#$7D; RET tail, with A already zero from MOV A,$54.
    data[first:first+12] = new
    data[branch] = relative(FLUSH, 2, FINISH+5)
    return bytes(data), dict(changes=[dict(offset=first, before=old.hex(), after=new.hex()),
        dict(offset=branch, before=bytes((compact[branch],)).hex(), after=bytes((data[branch],)).hex())],
        no_restart_entry=FINISH+5, invariant='Validity is set only while pending-mask bit is set; every pending flush clears it.',
        scope=__doc__)


def patch(original, layout):
    compact, detail = compact_patch(original, layout)
    engine, balanced = balance(compact)
    return engine, dict(detail, balanced_zero_path=balanced, scope=__doc__)


def build(parent, out):
    if out.exists():
        raise ValueError('Fresh candidate required')
    meta = json.loads((parent/'manifest.json').read_text())
    rom = parent/'native-cpu.sfc'; original = rom.read_bytes()
    if sha(rom) != meta['rom_sha256']:
        raise ValueError('Unbound parent')
    at = meta['sweep_driver_rom_offset']; size = meta['sweep_driver_layout']['engine_bytes']
    engine, detail = patch(original[at:at+size], meta['sweep_driver_layout'])
    image = bytearray(original); image[at:at+size] = engine; checksum(image)
    if len(engine) != size or any(a != b for i, (a, b) in enumerate(zip(original, image))
        if not (at <= i < at+size or 0xffdc <= i < 0xffe0)):
        raise ValueError('Changed upload extent or unrelated ROM content')
    out.mkdir()
    for p in parent.iterdir():
        if p.is_file():
            shutil.copy2(p, out/p.name)
    (out/'native-cpu.sfc').write_bytes(image); (out/'engine.bin').write_bytes(engine)
    paths = [Path(__file__), Path('tests/test_balanced_startup_game.py'),
             Path('tools/build_compact_startup_pitch.py'), Path('tools/build_inline_pitch_trial.py'),
             parent/'manifest.json', rom, out/'native-cpu.sfc', out/'engine.bin']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'), spc_sha256=hashlib.sha256(engine).hexdigest(),
        experimental_startup_pitch=dict(detail, parent=str(parent), release_ready=False,
            sources={str(p): sha(p) for p in paths}))
    (out/'manifest.json').write_text(json.dumps(meta, indent=2)+'\n')
    print(json.dumps(dict(rom_sha256=meta['rom_sha256'], spc_sha256=meta['spc_sha256'], scope=__doc__)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    build(**vars(p.parse_args()))
