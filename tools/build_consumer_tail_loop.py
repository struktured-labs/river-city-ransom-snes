"""Reduce empty wrap-tail scan cost without changing queue order or DMA deadlines."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.consumer_empty_tail import assemble as old_assemble
from tools.consumer_word_entry_fix import validate_entry


def assemble():
    with tempfile.TemporaryDirectory(prefix='rcr-tail-loop-') as temp:
        obj = Path(temp) / 'helper.o'; binary = Path(temp) / 'helper.bin'
        subprocess.run(['.deps/cc65/bin/ca65', '-o', str(obj), 'snes/consumer_tail_loop.asm'], check=True)
        subprocess.run(['.deps/cc65/bin/ld65', '-C', 'snes/consumer_linear_scan.cfg',
                        '-o', str(binary), str(obj)], check=True)
        return binary.read_bytes()


def build(parent, out):
    rom = parent / 'native-cpu.sfc'
    if out.exists() or sha(rom) != '976c2bacbdd9950cda35d07d608709e3366bcb483bc81bcb546d0dc49dec7157':
        raise ValueError('Exact3743 and fresh output required')
    original = rom.read_bytes(); validate_entry(original)
    old = old_assemble(); helper = assemble(); size = max(len(old), len(helper))
    if original[0x7380:0x7380+size] != old + b'\xff' * (size-len(old)):
        raise ValueError('Changed helper or occupied extension')
    image = bytearray(original)
    image[0x7380:0x7380+size] = helper + b'\xff' * (size-len(helper))
    checksum(image); out.mkdir(parents=True)
    for p in parent.iterdir():
        if p.is_file():
            shutil.copy2(p, out / p.name)
    (out / 'native-cpu.sfc').write_bytes(image)
    (out / 'tail-loop.bin').write_bytes(helper)
    sources = [Path(__file__), Path('snes/consumer_tail_loop.asm'), Path('snes/consumer_linear_scan.cfg'),
        Path('tools/consumer_empty_tail.py'), Path('snes/consumer_empty_tail.asm'),
        Path('tools/consumer_word_entry_fix.py'), Path('tools/build_inline_pitch_trial.py'),
        Path('.deps/cc65/bin/ca65'), Path('.deps/cc65/bin/ld65'), rom, parent / 'manifest.json']
    meta = json.loads((parent / 'manifest.json').read_text())
    meta.update(rom_sha256=sha(out / 'native-cpu.sfc'), experimental_consumer_tail_loop=dict(
        sources={str(p): sha(p) for p in sources}, before=old.hex(), helper=helper.hex(),
        release_ready=False, scope=__doc__))
    (out / 'manifest.json').write_text(json.dumps(meta, indent=2) + '\n')
    print(json.dumps(dict(out=str(out), bytes=len(helper), rom_sha256=meta['rom_sha256'])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    build(**vars(parser.parse_args()))
