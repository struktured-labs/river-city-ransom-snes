"""Execute native palette comparator against the original, including exit flags."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_palette_compare_unrolled import assemble, ADDRESS, HELPER, HOOK, ORIGINAL


def execute(core, out, db, dp, helper):
    out.mkdir(parents=True, exist_ok=False)
    for name, data in (('original', ORIGINAL), ('hook', HOOK), ('helper', helper)):
        (out/(name+'.bin')).write_bytes(data)
    subprocess.run(['.deps/cc65/bin/ca65', '-D', f'DATA_BANK={db}',
        '-D', f'DIRECT_PAGE={dp}', '--bin-include-dir', str(out), '-I', 'snes',
        '-o', str(out/'test.o'), 'snes/palette_compare_test.asm'], check=True)
    subprocess.run(['.deps/cc65/bin/ld65', '-C', 'snes/palette_compare_test.cfg',
        '-o', str(out/'test.bin'), str(out/'test.o')], check=True)
    program = (out/'test.bin').read_bytes()
    if len(program) != 0x8000:
        raise ValueError('Unexpected fixture size')
    for address, data in ((ADDRESS, ORIGINAL), (0xAB80, HOOK), (HELPER, helper)):
        if program[address-0x8000:address-0x8000+len(data)] != data:
            raise ValueError('Fixture changed tested machine code')
    image = bytearray(0x200000)
    image[0x8000:0x10000] = program
    checksum(image)
    (out/'test.sfc').write_bytes(image)
    run = subprocess.run([sys.executable, '-m', 'tools.smoke_libretro', '--core', str(core),
        '--rom', str(out/'test.sfc'), '--kind', 'adapter', '--frames', '10000',
        '--ram', str(out/'memory.ram'), '--receipt', str(out/'receipt.json')],
        capture_output=True, text=True, timeout=120)
    (out/'execution.log').write_text(run.stdout+run.stderr)
    if run.returncode:
        if 'Diagnostic failed: WRAM status=ff' in run.stderr:
            return dict(passed=False, reason='executed mismatch', db=db, dp=dp)
        raise RuntimeError(run.stdout+run.stderr)
    ram = (out/'memory.ram').read_bytes()
    if ram[0x600:0x603] != bytes((0, 17, 1)) or ram[0x1C60] != 1:
        raise ValueError('Case matrix did not finish')
    return dict(passed=True, cases=17*256, db=db, dp=dp)


def audit(core, candidate, out):
    paths = [Path(__file__), Path('tools/build_palette_compare_unrolled.py'),
        Path('tools/build_inline_pitch_trial.py'), Path('tools/smoke_libretro.py'),
        Path('snes/palette_compare_unrolled.asm'), Path('snes/palette_compare_unrolled.cfg'),
        Path('snes/palette_compare_test.asm'), Path('snes/palette_compare_test.cfg'),
        Path('snes/wram_clear.inc'), candidate/'native-cpu.sfc', candidate/'manifest.json', core]
    sources = {str(p): sha(p) for p in paths}
    out.mkdir(parents=True, exist_ok=False)
    helper = assemble(out)
    rom = (candidate/'native-cpu.sfc').read_bytes()
    if (sha(candidate/'native-cpu.sfc') != json.loads((candidate/'manifest.json').read_text())['rom_sha256']
            or rom[ADDRESS:ADDRESS+len(ORIGINAL)] != HOOK+ORIGINAL[3:]
            or rom[HELPER:HELPER+len(helper)] != helper):
        raise ValueError('Different actual helper/hook')
    def run(case):
        db, dp = case
        result = execute(core, out/f'db-{db:02x}-dp-{dp:04x}', db, dp, helper)
        print(json.dumps(result), flush=True)
        return result
    with ThreadPoolExecutor(max_workers=2) as pool:
        cases = list(pool.map(run, ((0, 0), (0, 0x1E00), (0x80, 0x1E00), (0x7E, 0))))
    if not all(c['passed'] for c in cases):
        raise ValueError('Helper differs from executed original')
    mutants = []
    for name, before, after in (
        ('wrong-source-word', bytes.fromhex('af003f7f'), bytes.fromhex('af023f7f')),
        ('lost-compare-flags', bytes.fromhex('08a2000028'), bytes.fromhex('eaa20000ea')),
        ('wrong-final-index', bytes.fromhex('a22000e02000'), bytes.fromhex('a21e00e02000'))):
        if len(before) != len(after) or helper.count(before) != 1:
            raise ValueError('Invalid mutation site')
        result = execute(core, out/name, 0, 0x1E00, helper.replace(before, after))
        if result['passed']:
            raise ValueError('Mutant survived: '+name)
        mutants.append(dict(name=name, **result))
    if any(sha(Path(p)) != h for p, h in sources.items()):
        raise ValueError('Source changed during oracle')
    report = dict(passed=True, cases=cases, mutants=mutants, sources=sources,
        artifacts={str(p.relative_to(out)): sha(p) for p in out.rglob('*') if p.is_file()},
        scope='17,408 executed cases. Equal palette and first mismatch at each of16 words; '
        '256 pattern/status seeds per position with single-bit differences cycling all16 bits. '
        'Native A16/X16 entry, PB C0, four DB/DP configurations. Compare A including hidden B, '
        'P/width, X/Y/SP/DB/DP, exit path, and unchanged32-byte source/cache. Patterns and flags '
        'are correlated, not their full cross product. No injected interrupts or CGRAM/game-speed proof.')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(passed=True, cases=17*256*4, mutants=len(mutants))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('core', 'candidate', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    audit(**vars(p.parse_args()))
