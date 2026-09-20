"""Guarded bounded-prefix scan optimization on the line32 audio candidate."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_consumer_suffix_hybrid import assemble as old_assemble
from tools.consumer_word_entry_fix import validate_entry

START = 0x4000


def assemble():
    with tempfile.TemporaryDirectory(prefix='rcr-prefix24-') as temp:
        obj = Path(temp)/'helper.o'; binary = Path(temp)/'helper.bin'
        subprocess.run(['.deps/cc65/bin/ca65','-I','snes','-o',str(obj),
                        'snes/consumer_prefix24.asm'],check=True)
        subprocess.run(['.deps/cc65/bin/ld65','-C','snes/consumer_prefix24.cfg',
                        '-o',str(binary),str(obj)],check=True)
        return binary.read_bytes()


def build(parent,out):
    rom = parent/'native-cpu.sfc'
    if out.exists() or sha(rom) != 'f68651c81acebf023e3def93c299a73b4db94cee47c18de99d292d38c94e9b10':
        raise ValueError('Exact3862 and fresh output required')
    original = rom.read_bytes(); validate_entry(original)
    old = old_assemble(); helper = assemble()
    if (original[0x7380:0x7380+len(old)] != old or
            original[START:START+len(helper)] != b'\xff'*len(helper)):
        raise ValueError('Changed parent helper or occupied extension')
    image = bytearray(original)
    image[START:START+len(helper)] = helper
    image[0x7380:0x7383] = bytes((0x4c,START&255,START>>8))
    checksum(image)
    changed = [i for i,(a,b) in enumerate(zip(original,image)) if a != b]
    if any(not (START <= i < START+len(helper) or 0x7380 <= i < 0x7383 or
                0xffdc <= i < 0xffe0) for i in changed):
        raise ValueError('Unrelated code change')
    out.mkdir(parents=True)
    for p in parent.iterdir():
        if p.is_file(): shutil.copyfile(p,out/p.name)
    (out/'native-cpu.sfc').write_bytes(image)
    (out/'prefix24.bin').write_bytes(helper)
    paths = [Path(__file__),Path('snes/consumer_prefix24.asm'),Path('snes/consumer_prefix24.cfg'),
        Path('snes/consumer_tail_loop.asm'),Path('snes/consumer_suffix_hybrid.asm'),
        Path('tools/build_consumer_suffix_hybrid.py'),Path('tools/consumer_word_entry_fix.py'),
        Path('tools/build_inline_pitch_trial.py'),Path('.deps/cc65/bin/ca65'),
        Path('.deps/cc65/bin/ld65'),rom,parent/'manifest.json']
    meta = json.loads((parent/'manifest.json').read_text())
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_consumer_prefix24=dict(
        sources={str(p):sha(p) for p in paths},changes=changed,release_ready=False,scope=__doc__))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),bytes=len(helper),rom_sha256=meta['rom_sha256'])))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):p.add_argument('--'+k,type=Path,required=True)
    build(**vars(p.parse_args()))
