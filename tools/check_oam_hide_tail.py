"""Execute every terminating sprite-count and all P bytes against original code."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_oam_hide_tail import assemble, ADDRESS, HELPER, HOOK, ORIGINAL


def execute(core, out, bank, db, dp, helper):
    out.mkdir(parents=True, exist_ok=False)
    for name, data in (('original', ORIGINAL), ('hook', HOOK), ('helper', helper)):
        (out/(name+'.bin')).write_bytes(data)
    subprocess.run(['.deps/cc65/bin/ca65', '-D', f'SOURCE_BANK={bank}',
        '-D', f'DATA_BANK={db}', '-D', f'DIRECT_PAGE={dp}', '--bin-include-dir', str(out),
        '-I', 'snes', '-o', str(out/'test.o'), 'snes/oam_hide_tail_test.asm'], check=True)
    subprocess.run(['.deps/cc65/bin/ld65', '-C', 'snes/oam_hide_tail_test.cfg',
        '-o', str(out/'test.bin'), str(out/'test.o')], check=True)
    program = (out/'test.bin').read_bytes()
    for address, data in ((ADDRESS, ORIGINAL), (0xDF00, HOOK), (HELPER, helper)):
        if program[address-0x7000:address-0x7000+len(data)] != data:
            raise ValueError('Fixture changed executed machine code')
    if len(program) != 0x9000:
        raise ValueError('Unexpected fixture size')
    image = bytearray(0x200000)
    for b in range(9):
        image[b*65536+0x7000:(b+1)*65536] = program
    checksum(image)
    (out/'test.sfc').write_bytes(image)
    run = subprocess.run([sys.executable, '-m', 'tools.smoke_libretro', '--core', str(core),
        '--rom', str(out/'test.sfc'), '--kind', 'adapter', '--frames', '30000',
        '--ram', str(out/'memory.ram'), '--receipt', str(out/'receipt.json')],
        capture_output=True, text=True, timeout=180)
    (out/'execution.log').write_text(run.stdout+run.stderr)
    result = dict(bank=bank, db=db, dp=dp)
    if run.returncode:
        if 'Diagnostic failed: WRAM status=ff' in run.stderr:
            return dict(passed=False, reason='executed mismatch', **result)
        raise RuntimeError(run.stdout+run.stderr)
    ram = (out/'memory.ram').read_bytes()
    if ram[0x600:0x603] != b'\0\0\1' or ram[0x1C60] != 1:
        raise ValueError('Case matrix did not finish')
    return dict(passed=True, cases=64*256, **result)


def audit(core, candidate, out):
    paths = [Path(__file__), Path('tools/build_oam_hide_tail.py'),
        Path('tools/build_inline_pitch_trial.py'), Path('tools/smoke_libretro.py'),
        Path('snes/oam_hide_tail.asm'), Path('snes/oam_hide_tail.cfg'),
        Path('snes/oam_hide_tail_test.asm'), Path('snes/oam_hide_tail_test.cfg'),
        Path('snes/wram_clear.inc'), candidate/'native-cpu.sfc', candidate/'manifest.json', core]
    sources = {str(p): sha(p) for p in paths}
    out.mkdir(parents=True, exist_ok=False)
    helper = assemble(out)
    rom = (candidate/'native-cpu.sfc').read_bytes()
    if sha(candidate/'native-cpu.sfc') != json.loads((candidate/'manifest.json').read_text())['rom_sha256']:
        raise ValueError('Changed candidate')
    for b in range(1, 9):
        if (rom[b*65536+HELPER:b*65536+HELPER+len(helper)] != helper or
                rom[b*65536+ADDRESS:b*65536+ADDRESS+len(ORIGINAL)] != HOOK+ORIGINAL[3:]):
            raise ValueError('Oracle differs from candidate code')
    def run(i):
        result = execute(core, out/f'bank-{0xc1+i:02x}', 0xc1+i, 0x81+i,
                         0x1B00 if i&1 else 0, helper)
        print(json.dumps(result), flush=True)
        return result
    with ThreadPoolExecutor(max_workers=2) as pool:
        cases = list(pool.map(run, range(8)))
    if not all(c['passed'] for c in cases):
        raise ValueError('Replacement differs from original')
    mutants = []
    for name, before, after in (
            ('wrong-hidden-y', b'\xa9\xf0\x7c', b'\xa9\xef\x7c'),
            ('lost-final-carry', b'\xa2\x04\xe0\x04', b'\xa2\x04\xe0\x05'),
            ('wrong-oam-slot', b'\x8d\xfc\x02', b'\x8d\xfd\x02')):
        if helper.count(before) != 1:
            raise ValueError('Ambiguous mutation site')
        result = execute(core, out/name, 0xc1, 0x81, 0x1B00, helper.replace(before, after))
        if result['passed']:
            raise ValueError('Mutant survived: '+name)
        mutants.append(dict(name=name, **result))
    if any(sha(Path(p)) != h for p, h in sources.items()):
        raise ValueError('Oracle source changed during execution')
    report = dict(passed=True, cases=cases, mutants=mutants, sources=sources,
        artifacts={str(p.relative_to(out)): sha(p) for p in out.rglob('*') if p.is_file()},
        scope='131,072 executed cases: all64 aligned sprite counts x all256 status bytes, '
        'eight program/data banks, alternating DP0/1B00. Compare all256 OAM bytes, A, hidden B, '
        'P, X, Y, SP, DP, DB, and source count. E1 forces M/X; no injected interrupts. '
        'Unaligned original counts do not terminate and are not run through this oracle. '
        'The production helper retains their original loop. Not a game-speed or audio pass.')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(passed=True, cases=64*256*8, mutants=len(mutants))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('core', 'candidate', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    audit(**vars(p.parse_args()))
