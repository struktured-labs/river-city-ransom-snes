"""Execute full/partial production OAM transfer macros against actual OAM."""
import argparse
import json
from pathlib import Path
import struct
import subprocess

from tools.benchmark_report import sha


def checksum(image):
    image[0xffdc:0xffe0] = bytes.fromhex('ffff0000')
    value = sum(image) & 65535
    struct.pack_into('<HH', image, 0xffdc, value ^ 65535, value)
    return image


def execute(core, rom, out, failure=None):
    out.mkdir()
    result = subprocess.run(['python3', 'tools/smoke_libretro.py', '--core', str(core),
        '--rom', str(rom), '--kind', 'adapter', '--frames', '300',
        '--ram', str(out/'memory.ram'), '--receipt', str(out/'receipt.json')],
        capture_output=True, text=True, timeout=60)
    (out/'run.log').write_text(result.stdout+result.stderr)
    if failure is None:
        if result.returncode:
            raise ValueError(result.stderr)
        ram = (out/'memory.ram').read_bytes()
        if int.from_bytes(ram[0x302:0x304], 'little') != 256:
            raise ValueError('Incomplete generation coverage')
        if ram[0x5000:0x5220] != ram[0x6000:0x6220]:
            raise ValueError('Final physical OAM mismatch')
    elif result.returncode == 0 or f'adapter case={failure}' not in result.stderr:
        raise ValueError('Mutation did not fail intended assertion')
    return {str(p):sha(p) for p in [rom, *sorted(out.iterdir())]}


def check(core, out):
    out.mkdir(parents=True, exist_ok=False)
    positives, mutants = [], []
    for enabled in (False, True):
        prefix = out/('half' if enabled else 'full')
        subprocess.run(['.deps/cc65/bin/ca65', '-g',
            *(['-D','EXPERIMENTAL_OAM_LIVE_HALF=1'] if enabled else []),
            '-o', str(prefix.with_suffix('.o')), 'snes/oam_live_half_test.asm'], check=True)
        subprocess.run(['.deps/cc65/bin/ld65', '-C','snes/native_boot.cfg',
            '-o',str(prefix.with_suffix('.bin')),str(prefix.with_suffix('.o'))], check=True)
        image = bytearray(2*1024*1024)
        image[0x8000:0x10000] = prefix.with_suffix('.bin').read_bytes()
        rom = prefix.with_suffix('.sfc')
        rom.write_bytes(checksum(image))
        positives.append(execute(core, rom, prefix))
    good = (out/'half.sfc').read_bytes()
    specs = [
        ('short-initial', bytes.fromhex('a22002adf01b'), bytes.fromhex('a20001adf01b'), 1),
        ('missing-latch', bytes.fromhex('a9018df01b'), bytes.fromhex('a901eaeaea'), 1),
        ('missing-dma', bytes.fromhex('8d0b42a9018df01b'), bytes.fromhex('eaeaeaa9018df01b'), 2),
        ('wrong-source', bytes.fromhex('a200508e0243'), bytes.fromhex('a202508e0243'), 2),
    ]
    for name, before, after, failure in specs:
        if good.count(before) != 1:
            raise ValueError('Nonunique mutation '+name)
        rom = out/(name+'.sfc')
        rom.write_bytes(checksum(bytearray(good.replace(before, after))))
        mutants.append(dict(name=name, failure=failure, artifacts=execute(core,rom,out/name,failure)))
    sources = [Path(__file__), Path('snes/oam_live_half_test.asm'), Path('snes/oam_live_half.inc'),
        Path('snes/native_boot.cfg'), Path('snes/wram_clear.inc'), Path('tools/smoke_libretro.py'), core,
        Path('.deps/cc65/bin/ca65'), Path('.deps/cc65/bin/ld65')]
    report = dict(passed=True, generations_per_variant=256, positives=positives, mutants=mutants,
        sources={str(p):sha(p) for p in sources},
        scope='Production transfer-size/completion macros, poisoned physical OAM, full initial '
              'publication then 255 changed live generations. Every generation reads all544 '
              'hardware OAM bytes. Not full producer/NMI scheduling or gameplay certification.')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(passed=True, generations=512, rejected_mutants=len(mutants))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--core', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    check(**vars(p.parse_args()))
