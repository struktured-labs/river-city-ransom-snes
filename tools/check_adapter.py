"""Positive and corrupted-CHR negative controls of real SNES adapter execution."""
import argparse
from pathlib import Path
import subprocess
import sys

try:
    from .build_runtime_test import build, ROOT
except ImportError:
    from build_runtime_test import build, ROOT


def check(core):
    out = ROOT / "build/runtime-test"
    build(out)
    command = [sys.executable, str(ROOT / "tools/smoke_libretro.py"), "--core", str(core),
               "--kind", "adapter", "--frames", "300"]
    subprocess.run(command + ["--rom", str(out / "adapter-test.sfc"),
                               "--receipt", str(out / "receipt.json")], check=True, timeout=30)
    # Preserve the valid cartridge; deliberately corrupt only a separate fixture.
    bad = bytearray((out / "adapter-test.sfc").read_bytes())
    bad[0xF0000 + 0x42 * 1024 + 0x15] ^= 1
    negative = out / "corrupted-chr.sfc"
    negative.write_bytes(bad)
    result = subprocess.run(command + ["--rom", str(negative)], capture_output=True, text=True, timeout=30)
    if not result.returncode or "WRAM status=ee, adapter case=2" not in result.stderr:
        raise RuntimeError("Corrupted CHR did not fail the expected executed adapter assertion")
    print("Adapter positive control passed; corrupted-CHR negative control failed at the expected assertion.")
    wrong_bank = bytearray((out / 'adapter-test.sfc').read_bytes())
    wrong_bank[0xF0000 + 64 * 1024 + 0x15] ^= 1
    bank_negative = out / 'corrupted-chr-boundary.sfc'
    bank_negative.write_bytes(wrong_bank)
    result = subprocess.run(command + ['--rom', str(bank_negative)], capture_output=True, text=True, timeout=30)
    if not result.returncode or 'WRAM status=ee, adapter case=13' not in result.stderr:
        raise RuntimeError('Corrupted CF/D0 boundary sentinel did not fail all-bank assertion 13')
    print('All 128 raw CHR banks read correctly; corrupted bank 64 fails case 13.')
    bulk_increment = bytes.fromhex('18a52c6901852ca52d6900852d60')
    original_bulk = (out / 'adapter-test.sfc').read_bytes()
    if original_bulk.count(bulk_increment) != 8:
        raise RuntimeError('Expected one bulk pointer increment per runtime bank')
    bad_bulk = out / 'wrong-bulk-increment.sfc'
    bad_bulk.write_bytes(original_bulk.replace(bulk_increment, bytes.fromhex('18a52c6902852ca52d6900852d60')))
    result = subprocess.run(command + ['--rom', str(bad_bulk)], capture_output=True, text=True, timeout=30)
    if not result.returncode or 'WRAM status=ee, adapter case=14' not in result.stderr:
        raise RuntimeError('Wrong bulk pointer increment did not fail assertion 14')
    print('Bulk writer latch/increment/register cases pass; wrong increment fails case 14.')
    short_copy = bytearray((out/'adapter-test.sfc').read_bytes())
    sequence = bytes.fromhex('a9ff00547e7e')
    if short_copy.count(sequence) != 8:
        raise RuntimeError('Expected one OAM block-copy per replicated runtime bank')
    short_copy = short_copy.replace(sequence, bytes.fromhex('a9fe00547e7e'))
    truncated = out/'truncated-oam.sfc'
    truncated.write_bytes(short_copy)
    result = subprocess.run(command + ['--rom', str(truncated)], capture_output=True, text=True, timeout=30)
    if not result.returncode or 'WRAM status=ee, adapter case=6' not in result.stderr:
        raise RuntimeError('Truncated OAM copy did not fail its executed byte oracle')
    print('255-byte OAM negative control failed; all 256 bytes are required.')
    symbols = {line.split()[2].lstrip('.'): int(line.split()[1], 16)
               for line in (out/'runtime.lbl').read_text().splitlines()}
    banked = b'\x4c' + symbols['done_banked'].to_bytes(2, 'little')
    plain = b'\x4c' + symbols['done'].to_bytes(2, 'little')
    original = (out/'adapter-test.sfc').read_bytes()
    fill_store = bytes.fromhex('9700c8d0fb')
    if original.count(fill_store) != 8:
        raise RuntimeError('Expected one page fill store loop per runtime bank')
    bad_fill = out/'missing-page-fill-store.sfc'
    bad_fill.write_bytes(original.replace(fill_store, bytes.fromhex('eaeac8d0fb')))
    result = subprocess.run(command + ['--rom', str(bad_fill)], capture_output=True, text=True, timeout=30)
    if not result.returncode or 'WRAM status=ee, adapter case=16' not in result.stderr:
        raise RuntimeError('Missing page fill store did not fail assertion 16')
    print('Page fill bytes/attribute dirty flags/wrap pass; missing store fails case 16.')
    dirty_stride = bytes.fromhex('98186908a8')
    if original.count(dirty_stride) != 8:
        raise RuntimeError('Expected one eight-byte dirty stride per runtime bank')
    bad_attributes = out/'page-fill-missing-attributes.sfc'
    bad_attributes.write_bytes(original.replace(dirty_stride, bytes.fromhex('98186920a8')))
    result = subprocess.run(command + ['--rom', str(bad_attributes)], capture_output=True, text=True, timeout=30)
    if not result.returncode or 'WRAM status=ee, adapter case=16' not in result.stderr:
        raise RuntimeError('Omitted attribute groups did not fail assertion 16')
    print('Incomplete attribute dirtiness also fails page fill case 16.')
    read_call = b'\x22' + symbols['dispatch_ppudata_read'].to_bytes(2, 'little') + b'\xC1'
    if original.count(read_call * 2) != 8:
        raise RuntimeError('Expected two consecutive reads in each bulk source helper')
    bad_source = out/'missing-bulk-buffer-read.sfc'
    bad_source.write_bytes(original.replace(read_call * 2, b'\xEA' * 4 + read_call))
    result = subprocess.run(command + ['--rom', str(bad_source)], capture_output=True, text=True, timeout=30)
    if not result.returncode or 'WRAM status=ee, adapter case=15' not in result.stderr:
        raise RuntimeError('Missing bulk dummy read did not fail assertion 15')
    print('Bulk reader buffer/latch/CPU/CHR cases pass; missing dummy read fails case 15.')
    if original.count(banked) != 8:
        raise RuntimeError('Expected one bank-retarget jump per runtime bank')
    missing_bank = out/'missing-bank-return.sfc'
    missing_bank.write_bytes(original.replace(banked, plain))
    result = subprocess.run(command + ['--rom', str(missing_bank)], capture_output=True, text=True, timeout=30)
    if not result.returncode or 'WRAM status=ee, adapter case=8' not in result.stderr:
        raise RuntimeError('Missing bank retarget did not fail executed bank assertion 8')
    print('C1→C2 retarget and ordinary C2 returns pass; missing retarget fails case 8.')
    pair = bytes.fromhex('18690185fd8d171c')
    if original.count(pair) != 8:
        raise RuntimeError('Expected one direct R7 calculation per runtime bank')
    wrong_pair = out/'wrong-direct-pair.sfc'
    wrong_pair.write_bytes(original.replace(pair, bytes.fromhex('18690085fd8d171c')))
    result = subprocess.run(command + ['--rom', str(wrong_pair)], capture_output=True, text=True, timeout=30)
    if not result.returncode or 'WRAM status=ee, adapter case=9' not in result.stderr:
        raise RuntimeError('Incorrect direct R7 did not fail pair assertion 9')
    print('All eight direct bank pairs preserve registers/state; wrong R7 fails case 9.')
    guard = bytes.fromhex('ad0a1c0d831cd00a')
    if original.count(guard) != 40:
        raise RuntimeError('Expected two generated I/O guards and three bulk helper guards per runtime bank')
    for label, replacement in (
            ('nmi-depth', bytes.fromhex('a900ea0d831cd00a')),
            ('bank-depth', bytes.fromhex('ad0a1ceaeaead00a'))):
        mutant = out/f'missing-{label}-guard.sfc'
        mutant.write_bytes(original.replace(guard, replacement))
        result = subprocess.run(command + ['--rom', str(mutant)], capture_output=True, text=True, timeout=30)
        if not result.returncode or 'WRAM status=ee, adapter case=10' not in result.stderr:
            raise RuntimeError(f'Missing {label} guard did not fail hardware NMI assertion 10')
    print('Generated I/O stub preserves registers and masks NMI; either missing guard fails case 10.')
    fast_write = b'\x4c' + symbols['ppu_write_data'].to_bytes(2, 'little')
    if original.count(fast_write) != 8:
        raise RuntimeError('Expected one fast PPUDATA entry jump per runtime bank')
    skipped = out/'missing-fast-write.sfc'
    skipped.write_bytes(original.replace(fast_write, plain))
    result = subprocess.run(command + ['--rom', str(skipped)], capture_output=True, text=True, timeout=30)
    if not result.returncode or 'WRAM status=ee, adapter case=10' not in result.stderr:
        raise RuntimeError('Skipped fast PPU write did not fail data/dirty-state assertion 10')
    print('Fast PPUDATA writes/increments/dirties correctly; skipped write fails case 10.')
    schedule = bytes.fromhex('ad791cf005ad201c3004')
    if original.count(schedule) != 8:
        raise RuntimeError('Expected one PPUMASK pipeline check per runtime bank')
    duplicate_prepare = out/'duplicate-mask-prepare.sfc'
    duplicate_prepare.write_bytes(original.replace(schedule, bytes.fromhex('ad791cf005ad201ceaea')))
    result = subprocess.run(command + ['--rom', str(duplicate_prepare)], capture_output=True, text=True, timeout=30)
    if not result.returncode or 'WRAM status=ee, adapter case=11' not in result.stderr:
        raise RuntimeError('Duplicate PPUMASK preparation did not fail scheduling assertion 11')
    print('PPUMASK prepares initial/offline loads and coalesces active pipelines; duplicate call fails case 11.')
    fast_read = b'\x4c' + symbols['ppu_read_data'].to_bytes(2, 'little')
    if original.count(fast_read) != 8:
        raise RuntimeError('Expected one fast PPUDATA read jump per runtime bank')
    skipped_read = out/'missing-fast-read.sfc'
    skipped_read.write_bytes(original.replace(fast_read, plain))
    result = subprocess.run(command + ['--rom', str(skipped_read)], capture_output=True, text=True, timeout=30)
    if not result.returncode or 'WRAM status=ee, adapter case=12' not in result.stderr:
        raise RuntimeError('Skipped fast read did not fail read-buffer assertion 12')
    print('Fast PPU read buffer/palette/increment/flags pass; skipped read fails case 12.')
    controls = ROOT / "build/controller-test"
    build(controls, controllers=True)
    control_cmd = command + ["--rom", str(controls / "adapter-test.sfc")]
    subprocess.run(control_cmd + ["--profile", "select-control", "--receipt", str(controls / "receipt.json")],
                   check=True, timeout=30)
    missing = subprocess.run(control_cmd, capture_output=True, text=True, timeout=30)
    if not missing.returncode or "WRAM status=ee, adapter case=5" not in missing.stderr:
        raise RuntimeError("Missing Select input did not fail the controller assertion")
    print("P1 Select/P2 Start serial routing passed; absent-input negative control failed correctly.")
    jump = ROOT / 'build/jump-test'
    build(jump, jump=True)
    jump_cmd = command + ['--rom', str(jump/'adapter-test.sfc')]
    for profile in ('jump-control', 'jump-swapped'):
        subprocess.run(jump_cmd + ['--profile', profile, '--receipt', str(jump/(profile+'.json'))], check=True, timeout=30)
    missing = subprocess.run(jump_cmd, capture_output=True, text=True, timeout=30)
    if not missing.returncode or 'WRAM status=ee, adapter case=5' not in missing.stderr:
        raise RuntimeError('Absent jump buttons did not fail the executed assertion')
    print('SNES A and B+Y produce identical NES A+B on both ports; absent-input control fails.')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", type=Path, required=True)
    check(parser.parse_args().core)
