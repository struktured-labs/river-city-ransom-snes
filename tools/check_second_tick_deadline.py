"""Execute camera deadline against real beam/NMI with cycle-consuming producer."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess

from tools.benchmark_report import sha
from tools.check_oam_live_half import checksum


def decision(line):
    return line < 194


def case(core, out, line, nops=0, guarded=True, mutation=None):
    out.mkdir(parents=True, exist_ok=False)
    helper = Path('snes/second_tick_deadline.inc').read_text()
    if mutation:
        before, after = mutation
        if helper.count(before) != 1:
            raise ValueError('Ambiguous deadline mutation')
        helper = helper.replace(before, after)
    (out/'second_tick_deadline.inc').write_text(helper)
    (out/'test.asm').write_bytes(Path('snes/second_tick_deadline_test.asm').read_bytes())
    subprocess.run(['.deps/cc65/bin/ca65', '-D', f'TARGET_LINE={line}',
        '-D', f'DELAY_NOPS={nops}', '-D', f'GUARDED={int(guarded)}', '-I', 'snes',
        '-o', str(out/'test.o'), str(out/'test.asm')], check=True, capture_output=True)
    subprocess.run(['.deps/cc65/bin/ld65', '-C', 'snes/native_boot.cfg',
        '-o', str(out/'test.bin'), str(out/'test.o')], check=True, capture_output=True)
    image = bytearray(2*1024*1024)
    image[0x8000:0x10000] = (out/'test.bin').read_bytes()
    (out/'test.sfc').write_bytes(checksum(image))
    subprocess.run(['python3', 'tools/smoke_libretro.py', '--core', str(core),
        '--rom', str(out/'test.sfc'), '--kind', 'adapter', '--frames', '120',
        '--ram', str(out/'memory.ram'), '--receipt', str(out/'receipt.json')],
        check=True, capture_output=True, timeout=30)
    ram = (out/'memory.ram').read_bytes()
    beam = int.from_bytes(ram[0x6006:0x6008], 'little')
    allowed = decision(beam) if guarded else True
    if ram[0x6008:0x600A] != bytes((not allowed, allowed)):
        raise ValueError('Wrong camera decision or lost retained ownership')
    if ram[0x6000:0x6006] != bytes.fromhex('5678341200ff'):
        raise ValueError('X/Y/DP/DB/SP corrupted')
    nmis, calls = ram[0x1BA1], ram[0x1BA0]
    finish = int.from_bytes(ram[0x600A:0x600C], 'little')
    nmi_line = int.from_bytes(ram[0x600C:0x600E], 'little')
    # High-bit cases test guard/ownership, not a new VBlank edge: they start
    # within VBlank and deliberately acknowledge the old edge before enabling.
    if line < 240 and guarded:
        if nmis != 1 or calls != 1 or ram[0x1B80] != 0:
            raise ValueError('Missing VBlank or non-exactly-once producer')
        if nmi_line != 240 or (allowed and finish >= 240):
            raise ValueError('Producer delayed the VBlank interrupt')
        if ram[0x1B83:0x1B87] != bytes((1, 0, not allowed, 0)):
            raise ValueError('Service/fallback accounting differs')
    if not guarded and line == 231:
        if not (finish < 60 and nmis == 0 and calls == 1):
            raise ValueError('Old missed-VBlank counterexample not reproduced')
    return dict(line=line, delay_nops=nops, guarded=guarded, decision_line=beam,
        allowed=allowed, finish_line=finish, nmis=nmis, nmi_line=nmi_line, calls=calls,
        pending=ram[0x1B80], sources={str(p):sha(p) for p in out.iterdir() if p.is_file()})


def run(core, out):
    out.mkdir(parents=True, exist_ok=False)
    matrix = [(line, delay) for line in (192,193,194,195,230,231,239,240,250,255,256,260)
              for delay in (0,20,60)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        cases = list(pool.map(lambda v:case(core,out/f'case-{v[0]}-{v[1]}',*v), matrix))
    negative = case(core, out/'old-missed-vblank', 231, guarded=False)
    mutants = []
    for name,line,mutation in (
        ('late-cutoff',231,('cmp #194','cmp #240')),
        ('lost-high-bit',256,('and #1','and #0')),
        ('drop-pending',231,('bcs @done','bcc :+\n    stz a:$1B80\n    rts\n:')),
        ('wrong-early-cutoff',193,('cmp #194','cmp #193')),
    ):
        try:
            case(core,out/name,line,mutation=mutation)
        except ValueError as error:
            mutants.append(dict(name=name,rejection=str(error)))
        else:
            raise ValueError('Deadline mutant survived: '+name)
    sources = [Path(__file__), Path('snes/second_tick_deadline.inc'),
        Path('snes/second_tick_deadline_test.asm'), Path('snes/second_tick_prepare.inc'),
        Path('snes/native_boot.cfg'), Path('snes/wram_clear.inc'),
        Path('tools/smoke_libretro.py'), Path('tools/check_oam_live_half.py'), core]
    report = dict(passed=True, cases=cases, old_failure=negative, mutants=mutants,
        sources={str(p):sha(p) for p in sources}, scope='Actual beam registers and hardware NMI with a cycle-burning bridge spy. '
        'Not a worst-case production graphics budget or whole-game qualification.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(cases),mutants=len(mutants),old_failure=negative['nmis'])))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','out'):p.add_argument('--'+name,type=Path,required=True)
    run(**vars(p.parse_args()))
