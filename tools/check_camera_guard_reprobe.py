"""Execute actual relinked guard/service/fallback bytes with a timed bridge spy."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_camera_guard_reprobe import HELPER


def fixture_source():
    source = Path('snes/second_tick_deadline_test.asm').read_text()
    replacements = (
        ('reset:\n', 'reset:\n    jml BANK*$10000+entry\nentry:\n'),
        ('video_prepare_bridge:\n', '.segment "BRIDGE"\nvideo_prepare_bridge:\n'),
        ('nmi:\n', '.segment "CODE"\nnmi:\n    jml BANK*$10000+nmi_body\nnmi_body:\n'),
        ('.include "second_tick_prepare.inc"', '.segment "SERVICE"\nsecond_tick_prepare_service:\n    .incbin "service.bin"\n.segment "FALLBACK"\nsecond_tick_prepare_fallback:\n    .incbin "fallback.bin"'),
        ('.include "second_tick_deadline.inc"', '.segment "GUARD"\nsecond_tick_prepare_camera:\n    .incbin "guard.bin"'))
    for before, after in replacements:
        if source.count(before) != 1:
            raise ValueError('Changed fixture template')
        source = source.replace(before, after)
    return source


def execute(core, out, image, helper, labels, bridge, line, delay, bank, guarded=True):
    out.mkdir(parents=True, exist_ok=False)
    service, fallback = labels['second_tick_prepare_service'], labels['second_tick_prepare_fallback']
    service_bytes = image[0x10000+service:0x10000+fallback]
    # This exact seventeen-byte fallback ends at the following runtime helper.
    fallback_bytes = image[0x10000+fallback:0x10000+fallback+17]
    if service_bytes[-5:] != b'\x22'+(0xC00000+bridge).to_bytes(3, 'little')+b'\x60':
        raise ValueError('Changed producer bridge call')
    for name, data in (('guard', helper), ('service', service_bytes), ('fallback', fallback_bytes)):
        (out/(name+'.bin')).write_bytes(data)
    (out/'test.asm').write_text(fixture_source())
    (out/'test.cfg').write_text('MEMORY { ROM: start=$2000,size=$E000,file=%O,fill=yes,fillval=$FF; }\n'
        f'SEGMENTS {{ SERVICE: load=ROM,type=ro,start=${service:04x}; '
        f'FALLBACK: load=ROM,type=ro,start=${fallback:04x}; '
        f'GUARD: load=ROM,type=ro,start=${HELPER:04x}; '
        f'BRIDGE: load=ROM,type=ro,start=${bridge:04x}; '
        'CODE: load=ROM,type=ro,start=$8500; HEADER: load=ROM,type=ro,start=$FFC0; '
        'VECTORS: load=ROM,type=ro,start=$FFE0; }\n')
    subprocess.run(['.deps/cc65/bin/ca65', '-D', f'TARGET_LINE={line}',
        '-D', f'DELAY_NOPS={delay}', '-D', f'GUARDED={int(guarded)}', '-D', f'BANK={bank}',
        '--bin-include-dir', str(out), '-I', 'snes', '-o', str(out/'test.o'), str(out/'test.asm')],
        check=True, capture_output=True)
    subprocess.run(['.deps/cc65/bin/ld65', '-C', str(out/'test.cfg'),
        '-o', str(out/'test.bin'), str(out/'test.o')], check=True, capture_output=True)
    program = (out/'test.bin').read_bytes()
    if len(program) != 0xE000:
        raise ValueError('Wrong fixture size')
    for address, data in ((HELPER, helper), (service, service_bytes), (fallback, fallback_bytes)):
        if program[address-0x2000:address-0x2000+len(data)] != data:
            raise ValueError('Fixture changed actual code')
    rom = bytearray(0x200000)
    for b in range(9):
        rom[b*65536+0x2000:(b+1)*65536] = program
    checksum(rom)
    (out/'test.sfc').write_bytes(rom)
    run = subprocess.run([sys.executable, '-m', 'tools.smoke_libretro', '--core', str(core),
        '--rom', str(out/'test.sfc'), '--kind', 'adapter', '--frames', '120',
        '--ram', str(out/'memory.ram'), '--receipt', str(out/'receipt.json')],
        check=True, capture_output=True, text=True, timeout=30)
    (out/'execution.log').write_text(run.stdout+run.stderr)
    ram = (out/'memory.ram').read_bytes()
    beam = int.from_bytes(ram[0x6006:0x6008], 'little')
    allowed = beam < 194 if guarded else True
    if ram[0x6008:0x600A] != bytes((not allowed, allowed)):
        raise ValueError('Wrong admission or lost pending job')
    if ram[0x6000:0x6006] != bytes.fromhex('5678341200ff'):
        raise ValueError('Corrupted X/Y/DP/DB/SP')
    nmis, calls = ram[0x1BA1], ram[0x1BA0]
    finish = int.from_bytes(ram[0x600A:0x600C], 'little')
    nmi_line = int.from_bytes(ram[0x600C:0x600E], 'little')
    if line < 240 and guarded:
        if nmis != 1 or calls != 1 or ram[0x1B80] or nmi_line != 240 or (allowed and finish >= 240):
            raise ValueError('Missed/delayed NMI or lost/duplicate producer service')
        if ram[0x1B83:0x1B87] != bytes((1, 0, not allowed, 0)):
            raise ValueError('Service accounting differs')
    if not guarded and line == 231 and not (finish < 60 and nmis == 0 and calls == 1):
        raise ValueError('Unguarded missing-interrupt control was not reproduced')
    return dict(line=line, delay=delay, bank=bank, guarded=guarded, decision_line=beam,
        allowed=allowed, finish_line=finish, nmis=nmis, nmi_line=nmi_line, calls=calls,
        pending=ram[0x1B80])


def audit(candidate, core, out):
    if out.exists():
        raise ValueError('Fresh oracle required')
    rom = candidate/'native-cpu.sfc'
    meta = json.loads((candidate/'manifest.json').read_text())
    image = rom.read_bytes()
    helper = (candidate/'guard.bin').read_bytes()
    spec = meta['experimental_camera_guard_reprobe']
    if sha(rom) != meta['rom_sha256']:
        raise ValueError('Changed candidate')
    for bank, site in enumerate(spec['sites'], 1):
        if (image[site:site+3] != b'\x20'+HELPER.to_bytes(2, 'little')
                or image[bank*65536+HELPER:bank*65536+HELPER+128] != helper):
            raise ValueError('Wrong actual guard/hook')
    symbols = lambda path: {r.split()[2].lstrip('.'): int(r.split()[1], 16)
                           for r in path.read_text().splitlines()}
    labels = symbols(candidate/'native_runtime.lbl')
    bridge = symbols(candidate/'native_boot.lbl')['video_prepare_bridge']
    paths = [Path(__file__), Path('snes/second_tick_deadline_test.asm'), Path('snes/wram_clear.inc'),
        Path('tools/build_camera_guard_reprobe.py'), Path('tools/build_inline_pitch_trial.py'),
        Path('tools/smoke_libretro.py'), rom, candidate/'manifest.json', candidate/'guard.bin',
        candidate/'native_runtime.lbl', candidate/'native_boot.lbl', core]
    sources = {str(p): sha(p) for p in paths}
    out.mkdir(parents=True)
    matrix = [(line, delay) for line in (192,193,194,195,230,231,239,240,250,255,256,260)
              for delay in (0,20,60)]
    def run(item):
        index, (line, delay) = item
        return execute(core, out/f'line-{line}-delay-{delay}', image, helper, labels, bridge,
                       line, delay, 0xC1+index%8)
    with ThreadPoolExecutor(max_workers=2) as pool:
        cases = list(pool.map(run, enumerate(matrix)))
    old = execute(core, out/'unguarded', image, helper, labels, bridge, 231, 0, 0xC7, False)
    mutants = []
    for name, line, before, after in (
        ('late-cutoff', 231, bytes.fromhex('c9c2'), bytes.fromhex('c9f0')),
        ('lost-high-bit', 256, bytes.fromhex('2901'), bytes.fromhex('2900')),
        ('wrong-early-cutoff', 193, bytes.fromhex('c9c2'), bytes.fromhex('c9c1'))):
        if helper.count(before) != 1:
            raise ValueError('Ambiguous mutation site')
        try:
            execute(core, out/name, image, helper.replace(before, after), labels, bridge,
                    line, 0, 0xC8)
        except ValueError as error:
            mutants.append(dict(name=name, rejection=str(error)))
        else:
            raise ValueError('Executed mutant survived')
    if any(sha(Path(p)) != h for p, h in sources.items()):
        raise ValueError('Source changed')
    result = dict(passed=True, cases=cases, unguarded=old, mutants=mutants, sources=sources,
        artifacts={str(p.relative_to(out)): sha(p) for p in out.rglob('*') if p.is_file()},
        scope='Actual cartridge guard, service and fallback bytes at linked addresses; timed graphics '
        'bridge spy replaces production work.36 real-beam boundary/phase cases across eight code '
        'banks, three mutants, unguarded lost-edge control. X/Y/DP/DB/SP and pending/service/NMI '
        'accounting checked. High-bit/VBlank cases test admission, not a new interrupt edge. '
        'This is NOT a production worst-case bound or full graphics/audio qualification.')
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(passed=True, cases=len(cases), mutants=len(mutants))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'core', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    audit(**vars(p.parse_args()))
