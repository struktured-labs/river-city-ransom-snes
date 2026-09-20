"""Execute original/direct APU stubs in pairs and check an independent oracle."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import struct
import subprocess
import sys

from tools.build_native import stub, direct_apu_stub
from tools.benchmark_report import sha
ROOT = Path(__file__).resolve().parents[1]


def expected(address, value, status, enabled, flags, length, *, sweep_events=False):
    packet = bytearray([0xaa] * 24)
    packet[21:23] = bytes((enabled, flags))
    register = address - 0x4000
    if 0 <= register < 24:
        packet[register] = value
        if register == 21:
            length &= value
        if register < 16 and register % 4 == 3:
            length |= (1 << (register // 4)) & enabled
            packet[22] |= 1 << (register // 4)
        if register in (2, 3):
            packet[22] |= 64
        if register in (6, 7):
            packet[22] |= 128
        if sweep_events:
            from tools.build_sweep_packet import metadata
            packet[20]=metadata(0xaa,register,value)
    return bytes((value, status | 0x30, 0x34, 0x56, 0x83, 0x34, 0x12, 0xc3, 0xff)) + packet + bytes((length,))


def case(core, out, addresses, values=range(256), mutation=None, *, sweep_events=False):
    out.mkdir(parents=True, exist_ok=False)
    matrix = [(address, v, (v ^ 0xc5) | 0x30, (v * 37 ^ 0x55) & 255,
               (v * 19 ^ 0xa5) & 255, (v >> 4) & 15)
              for address in addresses for v in values]
    if len(matrix) * 34 > 65536:
        raise ValueError('Fixture records exceed bank 7F')
    text = (ROOT / 'snes/direct_apu.inc').read_text()
    if mutation:
        old, new = mutation
        if text.count(old) != 1:
            raise ValueError('Ambiguous mutant')
        text = text.replace(old, new)
    (out / 'direct_apu.inc').write_text(text)
    (out / 'native_runtime.asm').write_text((ROOT / 'snes/native_runtime.asm').read_text())
    (out / 'direct_apu_cases.inc').write_text('\n'.join('.byte ' + ','.join(map(str,
        (a & 255, a >> 8, v, p, e, f, l))) for a, v, p, e, f, l in matrix) + '\n')
    ca65, ld65 = [str(ROOT / '.deps/cc65/bin' / name) for name in ('ca65', 'ld65')]
    defines=['-D','EXPERIMENTAL_SWEEP_EVENTS=1'] if sweep_events else []
    subprocess.run([ca65, '-g', *defines, '-D', 'EXPERIMENTAL_DIRECT_APU=1', '-D', 'video_prepare_bridge=32512',
        '-D', 'audio_publish_bridge=32512', '-I', str(out), '-I', str(ROOT / 'snes'),
        '-o', str(out / 'runtime.o'), str(out / 'native_runtime.asm')], check=True, capture_output=True)
    subprocess.run([ld65, '-C', str(ROOT / 'snes/native_runtime.cfg'), '-Ln', str(out / 'runtime.lbl'),
        '-o', str(out / 'runtime.bin'), str(out / 'runtime.o')], check=True, capture_output=True)
    symbols = {r.split()[2].lstrip('.'): int(r.split()[1], 16)
               for r in (out / 'runtime.lbl').read_text().splitlines()}
    legacy = stub(0x8d, 0x4000, symbols['dispatch_write'], dynamic_apu=True)
    fast = direct_apu_stub(symbols['direct_dynamic_apu'], legacy)
    subprocess.run([ca65, '-g', '-D', 'legacy_stub=24576', '-D', f'fast_stub={24576+len(legacy)}',
        '-I', str(out), '-I', str(ROOT / 'snes'), '-o', str(out / 'test.o'),
        str(ROOT / 'snes/direct_apu_test.asm')], check=True, capture_output=True)
    subprocess.run([ld65, '-C', str(ROOT / 'snes/native_boot.cfg'), '-Ln', str(out / 'test.lbl'),
        '-o', str(out / 'test.bin'), str(out / 'test.o')], check=True, capture_output=True)
    rom = bytearray([255] * 2097152)
    program = (out / 'test.bin').read_bytes()
    rom[0x8000:0x10000] = program
    for bank in range(1, 9):
        rom[bank*65536+0x8000:(bank+1)*65536] = program
        rom[bank*65536+0x2000:bank*65536+0x6000] = (out / 'runtime.bin').read_bytes()
        rom[bank*65536+0x6000:bank*65536+0x6000+len(legacy+fast)] = legacy + fast
    rom[0xffdc:0xffe0] = b'\xff\xff\0\0'
    total = sum(rom) & 65535
    struct.pack_into('<HH', rom, 0xffdc, total ^ 65535, total)
    (out / 'test.sfc').write_bytes(rom)
    result = subprocess.run([sys.executable, str(ROOT / 'tools/smoke_libretro.py'), '--core', str(core),
        '--rom', str(out / 'test.sfc'), '--kind', 'adapter', '--frames', '360', '--ram',
        str(out / 'memory.ram'), '--receipt', str(out / 'receipt.json')], capture_output=True, text=True, timeout=30)
    (out / 'execution.log').write_text(result.stdout + result.stderr)
    if result.returncode:
        raise ValueError('Executed ABI/legacy comparison failed: ' + result.stderr[-500:])
    ram = (out / 'memory.ram').read_bytes()
    if int.from_bytes(ram[0x602:0x604], 'little') != 7 * len(matrix):
        raise ValueError('Incomplete matrix')
    for i, row in enumerate(matrix):
        got = ram[0x10000+i*34:0x10000+(i+1)*34]
        target=expected(*row,sweep_events=sweep_events)
        if got != target:
            raise ValueError(f'Independent result differs at {row}: {got.hex()} expected {target.hex()}')
    return dict(cases=len(matrix), addresses=addresses, rom_sha256=sha(out / 'test.sfc'),
        receipt_sha256=sha(out / 'receipt.json'), ram_sha256=sha(out / 'memory.ram'))


def run(core, out):
    out.mkdir(parents=True, exist_ok=False)
    addresses = list(range(0x4000, 0x4014)) + [0x4015, 0x4017, 0x4018, 0x4020]
    jobs = [addresses[i:i+6] for i in range(0, len(addresses), 6)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda pair: case(core, out / f'batch-{pair[0]}', pair[1]), enumerate(jobs)))
    mutants = []
    for name, mutation in (
        ('lost-timer-reload', ('.byte $00,$00,$40,$41', '.byte $00,$00,$00,$01')),
        ('disabled-length-reload', ('    and a:$0A15', '    nop\n    nop\n    nop')),
        ('lost-enable-clear', ('    and a:$1CA1', '    ora a:$1CA1')),
        ('wrong-table-bank', ('@flags:\n    lda f:$C10000+direct_apu_flags,x',
                              '@flags:\n    lda direct_apu_flags,x')),
        ('wrong-value', ('    sta a:$0A00,x\n    txa', '    eor #1\n    sta a:$0A00,x\n    txa'))):
        try:
            case(core, out / name, [0x4002, 0x4003, 0x4015], range(64), mutation)
        except ValueError as error:
            mutants.append(dict(name=name, error=str(error)))
        else:
            raise ValueError('Mutant passed: ' + name)
    report = dict(passed=True, cases=sum(r['cases'] for r in results), batches=results, mutants=mutants,
        core_sha256=sha(core), sources={str(p): sha(p) for p in (Path(__file__), ROOT / 'snes/direct_apu.inc',
        ROOT / 'snes/direct_apu_test.asm', ROOT / 'snes/native_runtime.asm', ROOT / 'tools/build_native.py')},
        scope='Real E=1 paired legacy/direct stubs and independent APU state/ABI oracle. All byte values, '
        '17 accelerated registers and seven generic fallback addresses. Nonzero DP and mirrored DB. '
        'Does not certify hardware NMI edge timing, DSP synthesis, gameplay speed or audio fidelity.')
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(passed=True, cases=report['cases'], mutants=len(mutants))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--core', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    run(a.core, a.out)
