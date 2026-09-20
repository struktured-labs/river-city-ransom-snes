"""Execute signed-shift shortcut against original instructions, not a Python model."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_saturating_shift_trial import assemble, HOOK, HELPER
from tools.build_signed_shift_trial import ADDRESS, ORIGINAL


def execute(core, out, bank, flags, count, helper):
    out.mkdir(parents=True, exist_ok=False)
    for name, data in (('original', ORIGINAL), ('hook', HOOK), ('helper', helper)):
        (out/(name+'.bin')).write_bytes(data)
    subprocess.run(['.deps/cc65/bin/ca65', '-g', '-D', f'SOURCE_BANK={bank}',
        '-D', f'FLAGS={flags}', '-D', f'COUNT={count}', '--bin-include-dir', str(out),
        '-I', 'snes', '-o', str(out/'test.o'), 'snes/saturating_shift_test.asm'],
        check=True, capture_output=True)
    subprocess.run(['.deps/cc65/bin/ld65', '-C', 'snes/saturating_shift_test.cfg',
        '-o', str(out/'test.bin'), str(out/'test.o')], check=True, capture_output=True)
    program = (out/'test.bin').read_bytes()
    if (len(program) != 0x9000 or program[0xeeee-0x7000:0xeeee-0x7000+17] != ORIGINAL
            or program[ADDRESS-0x7000:ADDRESS-0x7000+18] != HOOK+b'\x60'
            or program[HELPER-0x7000:HELPER-0x7000+64] != helper):
        raise ValueError('Fixture changed tested machine code')
    image = bytearray(2097152)
    for b in range(9):
        image[b*65536+0x7000:(b+1)*65536] = program
    checksum(image)
    (out/'test.sfc').write_bytes(image)
    run = subprocess.run([sys.executable, '-m', 'tools.smoke_libretro', '--core', str(core),
        '--rom', str(out/'test.sfc'), '--kind', 'adapter', '--frames', '30000',
        '--ram', str(out/'memory.ram'), '--receipt', str(out/'receipt.json')],
        capture_output=True, text=True, timeout=180)
    (out/'execution.log').write_text(run.stdout+run.stderr)
    result = dict(bank=bank, flags=flags, count=count)
    if run.returncode:
        if 'Diagnostic failed: WRAM status=ff' in run.stderr:
            return dict(passed=False, reason='executed mismatch', **result)
        raise RuntimeError(run.stdout+run.stderr)
    ram = (out/'memory.ram').read_bytes()
    if ram[0x600:0x603] != b'\0\0\1' or ram[0x1c60] != 1:
        raise ValueError('Operand matrix did not finish')
    return dict(passed=True, operands=65536, **result)


def audit(core, candidate, out):
    sources = [Path(__file__), Path('tools/build_saturating_shift_trial.py'),
        Path('tools/build_signed_shift_trial.py'), Path('tools/build_inline_pitch_trial.py'),
        Path('tools/smoke_libretro.py'), Path('snes/saturating_shift_test.asm'),
        Path('snes/saturating_shift_test.cfg'), Path('snes/saturating_shift.asm'),
        Path('snes/saturating_shift.cfg'), Path('snes/wram_clear.inc'),
        candidate/'native-cpu.sfc',candidate/'manifest.json',core]
    hashes = {str(p):sha(p) for p in sources}
    out.mkdir(parents=True, exist_ok=False)
    helper = assemble(out)
    rom = (candidate/'native-cpu.sfc').read_bytes()
    meta = json.loads((candidate/'manifest.json').read_text())
    if meta['rom_sha256'] != sha(candidate/'native-cpu.sfc'):
        raise ValueError('Changed trial cartridge')
    for bank in range(1,9):
        if (rom[bank*65536+HELPER:bank*65536+HELPER+64] != helper or
                rom[bank*65536+ADDRESS:bank*65536+ADDRESS+17] != HOOK):
            raise ValueError('Executed helper is not the actual cartridge helper')
    # Zero means256 shifts. Cross every D/I/V combination with all words,
    # rotating through the eight replicated banks. Also test count boundaries.
    cases = [(0xc1+i,0x31|((i&1)<<3)|((i&2)<<1)|((i&4)<<4),0) for i in range(8)]
    cases += [(0xc1+i,0x7d,c) for i,c in enumerate((1,5,15,16,17,127,255))]
    def run(case):
        bank,flags,count = case
        result = execute(core,out/f'bank-{bank:02x}-count-{count}',bank,flags,count,helper)
        print(json.dumps(result),flush=True)
        return result
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run,cases))
    if not all(r['passed'] for r in results):
        raise ValueError('Real helper differs from original executed instructions')
    mutants = []
    # Exact instruction sites, not random corruption or assembler failures.
    for name, before, after in (
        ('wrong-sign',bytes.fromhex('a5270a'),bytes.fromhex('a5260a')),
        ('wrong-negative-value',bytes.fromhex('a9ff8526'),bytes.fromhex('a97f8526')),
        ('lost-final-zero',bytes.fromhex('a2004ccac3'),bytes.fromhex('a2014ccac3'))):
        if helper.count(before) < 1:
            raise ValueError('Mutation site missing')
        changed = helper.replace(before,after,1)
        r = execute(core,out/name,0xc1,0x7d,0,changed)
        if r['passed']:
            raise ValueError('Mutant survived: '+name)
        mutants.append(dict(name=name,**r))
    if any(sha(Path(p)) != h for p,h in hashes.items()):
        raise ValueError('Source changed during oracle')
    result = dict(passed=True,cases=results,mutants=mutants,sources=hashes,
        files={str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()},
        scope='983,040 executed word/count/flag cases. Compare A, hidden B, P, X, Y, '
        'stack, low/high operand bytes. E=1, DP=DB=0, no injected interrupts. '
        'Eight D/I/V combinations across eight banks at X=0, plus seven count boundaries. '
        'Not every count crossed with every flag/bank, and not a game or interrupt-race proof.')
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=True,operands=65536*len(results),mutants=len(mutants))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('core','candidate','out'):
        p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
