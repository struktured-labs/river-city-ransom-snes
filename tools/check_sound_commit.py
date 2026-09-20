"""Execute the original sound commit and fused replacement with independent checks."""
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
PREIMAGE = bytes.fromhex('99d607e004b00abd4c07d0118cf907f00698290f8df907b9d6074cf80760')


def expected(row, *, sweep_events=False):
    high, value, status, enabled, flags, length, channel, register, mute = row
    packet = bytearray([0xaa] * 24)
    packet[21:23] = bytes((enabled, flags))
    suppressed = channel < 4 and mute != 0
    result = mute if suppressed else value
    pointer = 0xa5 if suppressed else (register if channel < 4 else register & 15)
    if not suppressed and high == 0x40 and pointer < 24 and pointer not in (20, 22):
        packet[pointer] = value
        if pointer == 21:
            length &= value
        if pointer < 16 and pointer % 4 == 3:
            length |= (1 << (pointer // 4)) & enabled
            packet[22] |= 1 << (pointer // 4)
        if pointer in (2, 3):
            packet[22] |= 64
        if pointer in (6, 7):
            packet[22] |= 128
        if sweep_events:
            from tools.build_sweep_packet import metadata
            packet[20]=metadata(0xaa,pointer,value)
    status = (status & 0x7c) | (channel >= 4) | (result & 0x80) | (2 if result == 0 else 0) | 0x30
    return bytes((result, status, channel, register, 0x83, 0x34, 0x12, 0xc3, 0xff)) + packet + bytes((length,))


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Fixture substitution not unique: ' + old)
    return text.replace(old, new)


def case(core, out, matrix, mutation=None, pending_guards=None, *, sweep_events=False):
    out.mkdir(parents=True, exist_ok=False)
    record_size = 35 if pending_guards is not None else 34
    if len(matrix) * record_size > 65536:
        raise ValueError('Fixture records exceed bank 7F')
    source = (ROOT / 'snes/sound_commit.inc').read_text()
    if mutation:
        source = replace_once(source, *mutation)
    (out / 'sound_commit.inc').write_text(source)
    (out / 'native_runtime.asm').write_text((ROOT / 'snes/native_runtime.asm').read_text())
    fixture = (ROOT / 'snes/direct_apu_test.asm').read_text()
    fixture = replace_once(fixture, '    lda #1\n    sta a:$1C0A', '''    lda cases+7,x
    sta a:$060A
    lda cases+8,x
    sta a:$060B
    lda cases+9,x
    sta a:$060C
    ldx a:$060A
    lda a:$060C
    sta a:$074C,x
    lda #1
    sta a:$1C0A''')
    # X is still 16-bit at the mute store; ensure its high byte is zero.
    fixture = replace_once(fixture, '    ldx a:$060A', '    lda #0\n    sta a:$060D\n    rep #$20\n    .a16\n    lda a:$060A\n    and #$00FF\n    tax\n    sep #$20\n    .a8')
    for old, new in [('    ldx #$34', '    ldx a:$060A'), ('    ldy #$56', '    ldy a:$060B')]:
        if fixture.count(old) != 2:
            raise ValueError('Fixture register setup moved')
        fixture = fixture.replace(old, new)
    fixture = replace_once(fixture, '    adc #7', '    adc #10')
    if pending_guards is not None:
        depth, guard = pending_guards
        fixture = replace_once(fixture, '    lda #1\n    sta a:$1C0A',
            f'    lda #{depth}\n    sta a:$1C0A\n    lda #{guard}\n    sta a:$1C83')
        fixture = replace_once(fixture, '    lda #0\n    sta a:$1C20', '''    lda #$80
    sta a:$1C20
    stz a:$0609
    stz $4200
@active_before_edge:
    lda $4212
    bmi @active_before_edge
    lda $4210
@fresh_edge:
    lda $4212
    bpl @fresh_edge''')
        fixture = replace_once(fixture, 'legacy_done:\n', 'legacy_done:\n    stz $4200\n')
        fixture = replace_once(fixture, 'fast_done:\n', 'fast_done:\n    stz $4200\n')
        fixture = replace_once(fixture, '    sta f:$7E3021',
            '    sta f:$7E3021\n    lda a:$0609\n    sta f:$7E3022')
        fixture = fixture.replace('cpx #34', 'cpx #35').replace('cpy #34', 'cpy #35')
        fixture = replace_once(fixture, 'interrupt:\n    rti', '''interrupt:
    pha
    lda $4210
    inc a:$0609
    ; Deliberately change the source after the write: return A must come
    ; from its saved value, not a post-NMI read of mutable sound RAM.
    lda a:$07D6,y
    eor #$FF
    sta a:$07D6,y
    pla
    jml $C30000+interrupt_return
interrupt_return:
    rti''')
    (out / 'test.asm').write_text(fixture)
    (out / 'direct_apu_cases.inc').write_text('\n'.join('.byte ' + ','.join(map(str,
        (0xa5, high, v, p, e, f, l, x, y, m))) for high, v, p, e, f, l, x, y, m in matrix) + '\n')
    ca65, ld65 = [str(ROOT / '.deps/cc65/bin' / name) for name in ('ca65', 'ld65')]
    def execute(command):
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
    defines=['-D','EXPERIMENTAL_SWEEP_EVENTS=1'] if sweep_events else []
    execute([ca65, '-g', *defines, '-D', 'EXPERIMENTAL_DIRECT_APU=1', '-D', 'EXPERIMENTAL_SOUND_COMMIT=1',
        '-D', 'video_prepare_bridge=32512', '-D', 'audio_publish_bridge=32512', '-I', str(out),
        '-I', str(ROOT / 'snes'), '-o', str(out / 'runtime.o'), str(out / 'native_runtime.asm')])
    execute([ld65, '-C', str(ROOT / 'snes/native_runtime.cfg'), '-Ln', str(out / 'runtime.lbl'),
        '-o', str(out / 'runtime.bin'), str(out / 'runtime.o')])
    symbols = {r.split()[2].lstrip('.'): int(r.split()[1], 16)
               for r in (out / 'runtime.lbl').read_text().splitlines()}
    generic = stub(0x8d, 0x4000, symbols['dispatch_write'], dynamic_apu=True)
    direct = direct_apu_stub(symbols['direct_dynamic_apu'], generic)
    reference = bytearray(PREIMAGE)
    reference[-3:-1] = struct.pack('<H', 0x6000)
    execute([ca65, '-g', '-D', 'legacy_stub=26624', '-D', f'fast_stub={symbols["native_sound_commit"]}',
        '-I', str(out), '-I', str(ROOT / 'snes'), '-o', str(out / 'test.o'), str(out / 'test.asm')])
    execute([ld65, '-C', str(ROOT / 'snes/native_boot.cfg'), '-Ln', str(out / 'test.lbl'),
        '-o', str(out / 'test.bin'), str(out / 'test.o')])
    rom = bytearray([255] * 2097152)
    program = (out / 'test.bin').read_bytes()
    rom[0x8000:0x10000] = program
    for bank in range(1, 9):
        rom[bank*65536+0x8000:(bank+1)*65536] = program
        rom[bank*65536+0x2000:bank*65536+0x6000] = (out / 'runtime.bin').read_bytes()
        rom[bank*65536+0x6000:bank*65536+0x6000+len(direct)] = direct
        rom[bank*65536+0x6800:bank*65536+0x6800+len(reference)] = reference
    rom[0xffdc:0xffe0] = b'\xff\xff\0\0'
    total = sum(rom) & 65535
    struct.pack_into('<HH', rom, 0xffdc, total ^ 65535, total)
    (out / 'test.sfc').write_bytes(rom)
    result = subprocess.run([sys.executable, str(ROOT / 'tools/smoke_libretro.py'), '--core', str(core),
        '--rom', str(out / 'test.sfc'), '--kind', 'adapter', '--frames', '360', '--ram',
        str(out / 'memory.ram'), '--receipt', str(out / 'receipt.json')], capture_output=True, text=True, timeout=30)
    (out / 'execution.log').write_text(result.stdout + result.stderr)
    if result.returncode:
        raise ValueError('Executed ABI/reference comparison failed: ' + result.stderr[-500:])
    ram = (out / 'memory.ram').read_bytes()
    if int.from_bytes(ram[0x602:0x604], 'little') != 10 * len(matrix):
        raise ValueError('Incomplete matrix')
    for i, row in enumerate(matrix):
        got = ram[0x10000+i*record_size:0x10000+(i+1)*record_size]
        target = expected(row,sweep_events=sweep_events)
        if pending_guards is not None:
            service = pending_guards == (0, 0) and not (row[6] < 4 and row[8])
            target += bytes((int(service),))
        if got != target:
            raise ValueError(f'Independent result differs at {row}: {got.hex()} expected {target.hex()}')
    # Shadow values persist across cases; the original store happens even for
    # muted channels. Pointer/source overlap is deliberately excluded (Y<32).
    shadow = bytearray(32)
    for row in matrix:
        service = pending_guards == (0, 0) and not (row[6] < 4 and row[8])
        shadow[row[7]] = row[1] ^ (255 if service else 0)
    if ram[0x7d6:0x7f6] != shadow:
        raise ValueError('Source shadow differs')
    last = matrix[-1]
    pointer = 0xa5 if last[6] < 4 and last[8] else last[7] if last[6] < 4 else last[7] & 15
    if ram[0x7f9:0x7fb] != bytes((pointer, last[0])):
        raise ValueError('Dynamic pointer differs')
    return dict(cases=len(matrix), pending_guards=pending_guards,
                rom_sha256=sha(out / 'test.sfc'), receipt_sha256=sha(out / 'receipt.json'),
                ram_sha256=sha(out / 'memory.ram'))


def run(core, out):
    out.mkdir(parents=True, exist_ok=False)
    # All channel/Y combinations, byte values and two music suppression states.
    jobs = []
    for x in range(8):
        for mute in ((0, 0x80) if x < 4 else (0,)):
            for first in range(0, 32, 4):
                jobs.append([(0x40, v, (v ^ 0xc5) | 0x30, (v * 37 ^ 0x55) & 255,
                              (v * 19 ^ 0xa5) & 255, (v >> 4) & 15, x, y, mute)
                             for y in range(first, first+4) for v in range(256)])
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda p: case(core, out / f'batch-{p[0]}', p[1]), enumerate(jobs)))
        edge_rows = [(0x40, v, (v ^ 0xc5) | 0x30, 15, 0, 15, x, y, mute)
                     for x, mute in ((0, 0), (0, 128), (4, 0))
                     for y in (0, 3, 15, 21) for v in (0, 1, 128, 255)]
        results += list(pool.map(lambda guards: case(core, out / f'edge-{guards[0]}-{guards[1]}',
            edge_rows, pending_guards=guards), ((0, 0), (0, 1), (1, 0), (1, 1))))
    mutants = []
    mutation_rows = [(0x40, v, 0x30, 15, 0, 0, x, y, mute)
                     for x in (0, 4) for y in (3, 11, 19, 21, 27) for mute in (0, 0x80) for v in (0, 1, 127, 128, 255)]
    for name, mutation in (
        ('wrong-sfx-mask', ('    and #$0F\n    sta a:$07F9', '    and #$07\n    sta a:$07F9')),
        ('lost-music-suppression', ('    beq @music\n    rts', '    bra @music\n    rts')),
        ('wrong-shadow-value', ('    sta a:$07D6,y', '    eor #1\n    sta a:$07D6,y')),
        ('disabled-length-reload', ('    and a:$0A15', '    nop\n    nop\n    nop')),
        ('lost-enable-clear', ('    and a:$1CA1', '    ora a:$1CA1')),
        ('lost-caller-flags', ('    cpx #4\n    pla', '    clc\n    nop\n    pla'))):
        rows = mutation_rows + [(0x40, 0, 0x30, 0, 0, 15, 0, 21, 0), (0x40, 0, 0x30, 0, 0, 0, 0, 3, 0)]
        try:
            case(core, out / name, rows, mutation)
        except ValueError as error:
            mutants.append(dict(name=name, error=str(error)))
        else:
            raise ValueError('Mutant passed: ' + name)
    for name, mutation in (
        ('cleared-pending-edge', ('@enable:\n', '@enable:\n    lda $4210\n')),
        ('ignored-interrupt-owner', ('    lda a:$1C0A\n    bne @return\n    lda a:$1C83',
                                    '    lda #0\n    bne @return\n    lda #0')),
        ('post-nmi-source-reread', ('    pla\n    rts', '    pla\n    lda a:$07D6,y\n    rts'))):
        try:
            case(core, out / name, edge_rows, mutation,
                 pending_guards=(1, 0) if name == 'ignored-interrupt-owner' else (0, 0))
        except ValueError as error:
            mutants.append(dict(name=name, error=str(error)))
        else:
            raise ValueError('Mutant passed: ' + name)
    report = dict(passed=True, cases=sum(r['cases'] for r in results), batches=results, mutants=mutants,
        core_sha256=sha(core), sources={str(p): sha(p) for p in (Path(__file__), ROOT / 'snes/sound_commit.inc',
        ROOT / 'snes/direct_apu.inc', ROOT / 'snes/direct_apu_test.asm', ROOT / 'snes/native_runtime.asm',
        ROOT / 'tools/build_native.py')}, scope='Original helper versus fused replacement, E=1, all byte values, '
        'X=0..7/Y=0..31, music suppression, independent CPU/APU oracle, final shadow/pointer checks. '
        'Generic $4014/$4016 writes execute but their non-APU side effects are not independently checked. '
        '192 additional cases exercise fresh masked NMI edges with four ownership combinations and '
        'a synthetic handler changing sound-source RAM; exact service count and saved return A checked. '
        'Does not cover Y/source-pointer aliases, mapper fallback, full-game/physical NMI timing or fidelity.')
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(passed=True, cases=report['cases'], mutants=len(mutants))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--core', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    run(a.core, a.out)
