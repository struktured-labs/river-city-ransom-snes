"""Paired executed FF29 replacement, bank state/ABI oracle and mutants."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import struct
import subprocess
import sys
from tools.build_native import stub
from tools.benchmark_report import sha
ROOT = Path(__file__).resolve().parents[1]


def expected(fc, fd, fb, status, chr_gate=True, pending_nmi=False):
    bank = 0xc1 + ((fc & 15) >> 1)
    flags = (status & 0x7d) | (fb & 0x80) | (2 if fb == 0 else 0) | 0x30
    dirty = 1 if chr_gate and ((fc ^ 0x80) | fb) & 0x80 else fc & 4
    return bytes((fb, flags, 0x5a, 0xa5, bank ^ 0x40, 0, 0, bank, 255, 0,
                  fb, fc, fd, fc, fd, fb, bank, bank, (fc+1)&255, dirty, (fc>>1)&1, 0, 128, fb,
                  int(pending_nmi and fc & 3 == 0)))


def case(core, out, source_bank=3, values=range(256), chr_gate=True, mutation=None, pending_nmi=False):
    out.mkdir(parents=True, exist_ok=False)
    matrix = [(fc, ((fc*3)^255) & 255, fb, ((fc ^ 0xc5) & 0xc7) | 0x30)
              for fc in values for fb in (0, 7, 0x80, 0x87)]
    # FD is an unrestricted byte, independent of the mapped R6 pair.
    matrix = [(fc, fd & 255, fb, p) for fc, fd, fb, p in matrix]
    for name in ('native_runtime.asm', 'bank_restore.inc'):
        text = (ROOT/'snes'/name).read_text()
        if mutation and name == 'bank_restore.inc':
            old, new = mutation
            if text.count(old) != 1:
                raise ValueError('Ambiguous mutant')
            text = text.replace(old, new)
        (out/name).write_text(text)
    (out/'bank_restore_cases.inc').write_text('\n'.join('.byte '+','.join(map(str,r)) for r in matrix)+'\n')
    ca65, ld65 = [str(ROOT/'.deps/cc65/bin'/n) for n in ('ca65', 'ld65')]
    subprocess.run([ca65, '-g', '-D', 'EXPERIMENTAL_BANK_RESTORE=1', '-D', 'video_prepare_bridge=32512',
        '-D', 'audio_publish_bridge=32512', *(['-D', 'EXPERIMENTAL_CHR_DIRTY_GATE=1'] if chr_gate else []),
        '-I', str(out), '-I', str(ROOT/'snes'), '-o', str(out/'runtime.o'), str(out/'native_runtime.asm')],
        check=True, capture_output=True)
    subprocess.run([ld65, '-C', str(ROOT/'snes/native_runtime.cfg'), '-Ln', str(out/'runtime.lbl'),
        '-o', str(out/'runtime.bin'), str(out/'runtime.o')], check=True, capture_output=True)
    labels = {r.split()[2].lstrip('.'):int(r.split()[1],16) for r in (out/'runtime.lbl').read_text().splitlines()}
    select = stub(0x8d, 0x8000, labels['dispatch_write'])
    data = stub(0x8d, 0x8001, labels['dispatch_write'])
    subprocess.run([ca65, '-g', '-D', f'SOURCE_BANK={source_bank}', '-D', 'select_stub=24576',
        '-D', f'PENDING_NMI={int(pending_nmi)}',
        '-D', f'data_stub={24576+len(select)}', '-D', f'native_bank_restore={labels["native_bank_restore"]}',
        '-I', str(out), '-I', str(ROOT/'snes'), '-o', str(out/'test.o'), str(ROOT/'snes/bank_restore_test.asm')],
        check=True, capture_output=True)
    subprocess.run([ld65, '-C', str(ROOT/'snes/native_boot.cfg'), '-Ln', str(out/'test.lbl'),
        '-o', str(out/'test.bin'), str(out/'test.o')], check=True, capture_output=True)
    rom = bytearray([255]*2097152)
    program = (out/'test.bin').read_bytes()
    rom[0x8000:0x10000] = program
    for bank in range(1,9):
        rom[bank*65536+0x8000:(bank+1)*65536] = program
        rom[bank*65536+0x2000:bank*65536+0x6000] = (out/'runtime.bin').read_bytes()
        rom[bank*65536+0x6000:bank*65536+0x6000+len(select+data)] = select+data
    rom[0xffdc:0xffe0] = b'\xff\xff\0\0'
    total=sum(rom)&65535
    struct.pack_into('<HH',rom,0xffdc,total^65535,total)
    (out/'test.sfc').write_bytes(rom)
    result=subprocess.run([sys.executable,'tools/smoke_libretro.py','--core',str(core),'--rom',str(out/'test.sfc'),
        '--kind','adapter','--frames','360','--ram',str(out/'memory.ram'),'--receipt',str(out/'receipt.json')],
        capture_output=True,text=True,timeout=30)
    (out/'execution.log').write_text(result.stdout+result.stderr)
    if result.returncode:
        raise ValueError('Executed restore failed: '+result.stderr[-450:])
    ram=(out/'memory.ram').read_bytes()
    if int.from_bytes(ram[0x602:0x604],'little')!=len(matrix)*4:
        raise ValueError('Incomplete matrix')
    for i,row in enumerate(matrix):
        got=ram[0x10000+i*25:0x10000+(i+1)*25]
        if got!=expected(*row,chr_gate,pending_nmi):
            raise ValueError(f'Independent bank oracle differs at {row}: {got.hex()} expected {expected(*row,chr_gate,pending_nmi).hex()}')
    return dict(cases=len(matrix),source_bank=source_bank,chr_gate=chr_gate,pending_nmi=pending_nmi,rom_sha256=sha(out/'test.sfc'),
        ram_sha256=sha(out/'memory.ram'),receipt_sha256=sha(out/'receipt.json'))


def run(core,out):
    out.mkdir(parents=True,exist_ok=False)
    jobs=[(bank,gate) for bank in range(1,9) for gate in (False,True)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda pair:case(core,out/f'bank-{pair[0]}-gate-{int(pair[1])}',
            source_bank=pair[0],chr_gate=pair[1]),jobs))
        results += list(pool.map(lambda bank:case(core,out/f'pending-bank-{bank}',source_bank=bank,
            values=range(16),pending_nmi=True),range(1,9)))
    mutants=[]
    for name,mutation in (
        ('wrong-bank',('    adc #$C1','    adc #$C2')),
        ('wrong-data-bank',('    eor #$40','    eor #$41')),
        ('lost-dirty',('    sta a:$1CBB','    nop\n    nop\n    nop')),
        ('wrong-r7',('    lda $FD','    lda $FC')),
        ('lost-flags',('    plp\n    lda $FB','    pla\n    lda $FB')),
        ('cleared-pending-edge',('native_bank_restore_exit:\n','native_bank_restore_exit:\n    lda $4210\n')),
        ('ignored-interrupt-owner',('    lda a:$1C0A\n    ora a:$1C83','    lda #0\n    ora #0'))):
        try:case(core,out/name,values=range(16),mutation=mutation,
                 pending_nmi=name in ('cleared-pending-edge','ignored-interrupt-owner'))
        except ValueError as error:mutants.append(dict(name=name,error=str(error)))
        else:raise ValueError('Unsafe mutation survived: '+name)
    report=dict(passed=True,cases=sum(r['cases'] for r in results),batches=results,mutants=mutants,
        core_sha256=sha(core),sources={str(p):sha(p) for p in (Path(__file__),ROOT/'tools/build_native.py',
            ROOT/'snes/native_runtime.asm',ROOT/'snes/bank_restore.inc',ROOT/'snes/bank_restore_test.asm')},
        scope='Paired original five-write mapper sequence and direct helper, all 256 R6 values, '
        'all eight source/target banks, four final selectors, both CHR-dirty policies. Caller D=0; '
        'flags, mapper state, banked return and interrupt-ownership counters match. '
        '512 cases additionally generate a fresh masked hardware NMI, checking exactly one service '
        'only when both ownership guards permit it, plus correct banked RTI/caller state. '
        'This uses a small synthetic NMI body, not full-game or physical-hardware certification.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=report['cases'],mutants=len(mutants))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','out'):p.add_argument('--'+name,type=Path,required=True)
    run(**vars(p.parse_args()))
