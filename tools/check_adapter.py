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
    build(out, ring_pointer_cache=True)
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
    bank_image = (out/'adapter-test.sfc').read_bytes()
    bank_xor = bytes.fromhex('8d8a1c494048ab')
    if bank_image.count(bank_xor) != 8:
        raise RuntimeError('Expected one program/data bank conversion per runtime bank')
    wrong_xor = out/'wrong-bank-xor.sfc'
    wrong_xor.write_bytes(bank_image.replace(bank_xor, bytes.fromhex('8d8a1c494148ab')))
    result = subprocess.run(command + ['--rom', str(wrong_xor)], capture_output=True, text=True, timeout=30)
    if not result.returncode or 'WRAM status=00, adapter case=9' not in result.stderr:
        raise RuntimeError('Wrong data-bank conversion did not halt the bank-tag check in case 9')
    print('All eight program/data bank mappings pass; wrong XOR halts at case 9.')
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
    for name, transfer, wrong in (('stx-wrong-register', '8a', '98'), ('sty-wrong-register', '98', '8a')):
        good = bytes.fromhex('9c00420848' + transfer + '8d221b22')
        replacement = bytes.fromhex('9c00420848' + wrong + '8d221b22')
        if original.count(good) != 8:
            raise RuntimeError('Expected one specialized register-store stub per bank')
        path = out / (name + '.sfc')
        path.write_bytes(original.replace(good, replacement))
        result = subprocess.run(command + ['--rom', str(path)], capture_output=True, text=True, timeout=30)
        if not result.returncode or 'WRAM status=ee, adapter case=28' not in result.stderr:
            raise RuntimeError('Wrong PPUDATA source register did not fail executed case 28')
    print('Specialized STX/STY PPUDATA ABI and data pass; wrong registers fail case 28.')
    literal_buffer = bytes.fromhex('a7088d2a1ca5228524')
    if original.count(literal_buffer) != 8:
        raise RuntimeError('Expected one literal lookahead buffer update per bank')
    path = out / 'literal-lost-read-buffer.sfc'
    path.write_bytes(original.replace(literal_buffer, bytes.fromhex('a708eaeaeaa5228524')))
    result = subprocess.run(command + ['--rom', str(path)], capture_output=True, text=True, timeout=30)
    if not result.returncode or 'WRAM status=ee, adapter case=30' not in result.stderr:
        raise RuntimeError('Lost literal lookahead did not fail executed case 30')
    print('Literal copied bytes, aliases, ABI and fallbacks pass; lost read buffer fails case 30.')
    for name, good, replacement in (
        ('rect-skipped-store', bytes.fromhex('8700a519'), bytes.fromhex('eaeaa519')),
        ('rect-wrong-segment', bytes.fromhex('ad261c2907d0026419'), bytes.fromhex('ad261c291fd0026419')),
        ('rect-missing-page-remap', bytes.fromhex('ee271c20')+symbols['ppu_pointer'].to_bytes(2,'little'),
         bytes.fromhex('ee271ceaeaea')),
    ):
        if original.count(good)!=(8 if name == 'rect-missing-page-remap' else 16):
            raise RuntimeError('Cannot identify rectangular-fill mutation in every bank')
        path=out/(name+'.sfc')
        path.write_bytes(original.replace(good,replacement))
        result=subprocess.run(command+['--rom',str(path)],capture_output=True,text=True,timeout=30)
        if not result.returncode or 'WRAM status=ee, adapter case=26' not in result.stderr:
            raise RuntimeError('Rectangular fill mutation did not fail executed case 26')
    print('Rectangular fill store, attribute-segment and page-remap mutations fail case 26.')
    for name, good, replacement in (
        ('repeat-lost-height-width',bytes.fromhex('68851d68851cad1b1b'),bytes.fromhex('68851e68851cad1b1b')),
        ('repeat-lost-flags',bytes.fromhex('ad1b1b48ad1a1b28'),bytes.fromhex('ad1b1b4828ad1a1b')),
    ):
        if original.count(good)!=8:
            raise RuntimeError('Cannot identify repeated-run return mutation')
        path=out/(name+'.sfc')
        path.write_bytes(original.replace(good,replacement))
        result=subprocess.run(command+['--rom',str(path)],capture_output=True,text=True,timeout=30)
        if not result.returncode or 'WRAM status=ee, adapter case=27' not in result.stderr:
            raise RuntimeError('Repeated-run mutation did not fail case 27')
    print('Repeated-run counter and return-flag mutations fail case 27.')
    palette_alias = bytes.fromhex('a500291f85002903d006a500290f8500')
    if original.count(palette_alias) != 8:
        raise RuntimeError('Expected one palette alias mapper per runtime bank')
    unaliased = out/'unaliased-palette.sfc'
    unaliased.write_bytes(original.replace(palette_alias, palette_alias[:3] + b'\xff' + palette_alias[4:]))
    result = subprocess.run(command + ['--rom', str(unaliased)], capture_output=True, text=True, timeout=30)
    if not result.returncode or 'WRAM status=ee, adapter case=20' not in result.stderr:
        raise RuntimeError('Disabled palette alias did not fail executed case 20')
    print('All 256 palette addresses alias on reads/writes; disabled mapping fails case 20.')
    attribute_restore = bytes.fromhex('68852d68852c68851d68851c68851b')
    if original.count(attribute_restore) != 8:
        raise RuntimeError('Expected one attribute-fill state restore per runtime bank')
    path = out / 'attribute-lost-destination.sfc'
    path.write_bytes(original.replace(attribute_restore, attribute_restore.replace(bytes.fromhex('852d'), bytes.fromhex('852e'))))
    result = subprocess.run(command + ['--rom', str(path)], capture_output=True, text=True, timeout=30)
    if not result.returncode or 'WRAM status=ee, adapter case=29' not in result.stderr:
        raise RuntimeError('Lost attribute-fill destination did not fail executed case 29')
    print('Attribute fill bytes, ABI, aliases and enabled fallback pass; lost state fails case 29.')
    palette_refill = bytes.fromhex('ad261c8500a92f850120') + symbols['nametable_pointer'].to_bytes(2, 'little') + bytes.fromhex('a7008d2a1c')
    if original.count(palette_refill) != 8:
        raise RuntimeError('Expected one palette read-buffer refill per runtime bank')
    wrong_refill = out/'palette-buffer-wrong-page.sfc'
    wrong_refill.write_bytes(original.replace(palette_refill, palette_refill.replace(b'\xa9\x2f', b'\xa9\x2b')))
    result = subprocess.run(command + ['--rom', str(wrong_refill)], capture_output=True, text=True, timeout=30)
    if not result.returncode or 'WRAM status=ee, adapter case=21' not in result.stderr:
        raise RuntimeError('Wrong palette buffer page did not fail executed case 21')
    print('Palette reads refill from all 256 underlying bytes; wrong page fails case 21.')
    snapshot_zero = bytes.fromhex('9d001dc900f002a9019d801e')
    if original.count(snapshot_zero) != 8:
        raise RuntimeError('Expected one explicit snapshot-zero test per bank')
    bad_snapshot = out/'snapshot-clean-row-pending.sfc'
    bad_snapshot.write_bytes(original.replace(snapshot_zero, snapshot_zero[:3] + b'\xEA\xEA' + snapshot_zero[5:]))
    result = subprocess.run(command + ['--rom', str(bad_snapshot)], capture_output=True, text=True, timeout=30)
    if not result.returncode or 'WRAM status=ee, adapter case=19' not in result.stderr:
        raise RuntimeError('False pending clean row did not fail transition assertion 19')
    bulk_store = bytes.fromhex('a91beba9005b20') + symbols['ppu_pointer'].to_bytes(2, 'little') + bytes.fromhex('a522c700f0058700')
    if original.count(bulk_store) != 8:
        raise RuntimeError('Expected one direct bulk PPU store per runtime bank')
    missing_store = out/'missing-bulk-ppu-store.sfc'
    missing_store.write_bytes(original.replace(bulk_store, bulk_store[:-2] + b'\xEA\xEA'))
    result = subprocess.run(command + ['--rom', str(missing_store)], capture_output=True, text=True, timeout=30)
    if not result.returncode or 'WRAM status=ee, adapter case=14' not in result.stderr:
        raise RuntimeError('Missing direct bulk PPU store did not fail assertion 14')
    redundant_dirty = out/'redundant-bulk-dirty.sfc'
    redundant_dirty.write_bytes(original.replace(bulk_store, bulk_store[:-4] + b'\xEA\xEA' + bulk_store[-2:]))
    result = subprocess.run(command + ['--rom', str(redundant_dirty)], capture_output=True, text=True, timeout=30)
    if not result.returncode or 'WRAM status=ee, adapter case=14' not in result.stderr:
        raise RuntimeError('Redundant unchanged-byte dirty work did not fail assertion 14')
    reload_flag = bytes.fromhex('a9400d160a8d160a')
    if original.count(reload_flag) != 8:
        raise RuntimeError('Expected one pulse-0 period reload flag per runtime bank')
    bad_reload = out/'missing-pulse-reload.sfc'
    bad_reload.write_bytes(original.replace(reload_flag, bytes.fromhex('a9000d160a8d160a')))
    result = subprocess.run(command + ['--rom', str(bad_reload)], capture_output=True, text=True, timeout=30)
    if not result.returncode or 'WRAM status=ee, adapter case=18' not in result.stderr:
        raise RuntimeError('Missing pulse reload flag did not fail assertion 18')
    print('Pulse timer writes flag both sweep reloads; omitted flag fails case 18.')
    eligible = bytes.fromhex('2d150a0da11c8da11c')
    if original.count(eligible) != 8:
        raise RuntimeError('Expected one length eligibility update per bank')
    invalid_reload = out/'disabled-length-reload.sfc'
    invalid_reload.write_bytes(original.replace(eligible, b'\x0D' + eligible[1:]))
    result = subprocess.run(command + ['--rom', str(invalid_reload)], capture_output=True, text=True, timeout=30)
    if not result.returncode or 'WRAM status=ee, adapter case=25' not in result.stderr:
        raise RuntimeError('Disabled length reload did not fail case 25')
    ring_store = bytes.fromhex('bd4505c700f0078700')
    if original.count(ring_store) != 8:
        raise RuntimeError('Expected one ring byte store per runtime bank')
    bad_ring = out/'missing-ring-store.sfc'
    bad_ring.write_bytes(original.replace(ring_store, ring_store[:-2] + bytes.fromhex('eaea')))
    result = subprocess.run(command + ['--rom', str(bad_ring)], capture_output=True, text=True, timeout=30)
    if not result.returncode or 'WRAM status=ee, adapter case=17' not in result.stderr:
        raise RuntimeError('Missing graphics ring store did not fail assertion 17')
    print('Graphics ring wrap/stride/flags cases pass; missing store fails case 17.')
    redundant_ring = out/'redundant-ring-dirty.sfc'
    redundant_ring.write_bytes(original.replace(ring_store, ring_store[:-4] + b'\xEA\xEA' + ring_store[-2:]))
    result = subprocess.run(command + ['--rom', str(redundant_ring)], capture_output=True, text=True, timeout=30)
    if not result.returncode or 'WRAM status=ee, adapter case=17' not in result.stderr:
        raise RuntimeError('Redundant unchanged ring work did not fail case 17')
    cached_ring_store = bytes.fromhex('bf450500c700f0078700')
    if original.count(cached_ring_store) != 8:
        raise RuntimeError('Expected one cached ring byte store per runtime bank')
    bad_cached_ring = out/'missing-cached-ring-store.sfc'
    bad_cached_ring.write_bytes(original.replace(
        cached_ring_store, cached_ring_store[:-2] + bytes.fromhex('eaea')))
    result = subprocess.run(command + ['--rom', str(bad_cached_ring)], capture_output=True,
                            text=True, timeout=30)
    if not result.returncode or 'WRAM status=ee, adapter case=17' not in result.stderr:
        raise RuntimeError('Missing cached graphics ring store did not fail assertion 17')
    redundant_cached_ring = out/'redundant-cached-ring-dirty.sfc'
    redundant_cached_ring.write_bytes(original.replace(
        cached_ring_store,
        cached_ring_store[:-4] + b'\xEA\xEA' + cached_ring_store[-2:]))
    result = subprocess.run(command + ['--rom', str(redundant_cached_ring)],
                            capture_output=True, text=True, timeout=30)
    if not result.returncode or 'WRAM status=ee, adapter case=17' not in result.stderr:
        raise RuntimeError('Redundant cached ring work did not fail case 17')
    print('Cached ring linear/page-wrap path passes; store and unchanged controls fail case 17.')
    fill_store = bytes.fromhex('9700c8d0fb')
    if original.count(fill_store) != 8:
        raise RuntimeError('Expected one page fill store loop per runtime bank')
    bad_fill = out/'missing-page-fill-store.sfc'
    bad_fill.write_bytes(original.replace(fill_store, bytes.fromhex('eaeac8d0fb')))
    result = subprocess.run(command + ['--rom', str(bad_fill)], capture_output=True, text=True, timeout=30)
    if not result.returncode or 'WRAM status=ee, adapter case=16' not in result.stderr:
        raise RuntimeError('Missing page fill store did not fail assertion 16')
    print('Page fill bytes/attribute dirty flags/wrap pass; missing store fails case 16.')
    dirty_stride = bytes.fromhex('98186506a8')
    if original.count(dirty_stride) != 8:
        raise RuntimeError('Expected one page-dependent dirty stride per runtime bank')
    bad_attributes = out/'page-fill-missing-attributes.sfc'
    bad_attributes.write_bytes(original.replace(dirty_stride, bytes.fromhex('98186920a8')))
    result = subprocess.run(command + ['--rom', str(bad_attributes)], capture_output=True, text=True, timeout=30)
    if not result.returncode or 'WRAM status=ee, adapter case=16' not in result.stderr:
        raise RuntimeError('Omitted attribute groups did not fail assertion 16')
    print('Incomplete attribute dirtiness also fails page fill case 16.')
    read_call = b'\x20' + symbols['ppu_read_buffer'].to_bytes(2, 'little')
    if original.count(read_call * 2) != 8:
        raise RuntimeError('Expected two consecutive reads in each bulk source helper')
    bad_source = out/'missing-bulk-buffer-read.sfc'
    bad_source.write_bytes(original.replace(read_call * 2, b'\xEA' * 3 + read_call))
    result = subprocess.run(command + ['--rom', str(bad_source)], capture_output=True, text=True, timeout=30)
    if not result.returncode or 'WRAM status=ee, adapter case=15' not in result.stderr:
        raise RuntimeError('Missing bulk dummy read did not fail assertion 15')
    print('Bulk reader buffer/latch/CPU/CHR cases pass; missing dummy read fails case 15.')
    read_restore = read_call * 2 + bytes.fromhex('2bfa28')
    if original.count(read_restore) != 8:
        raise RuntimeError('Expected one bulk read flags restore in each runtime bank')
    bad_flags = out/'missing-bulk-read-flags.sfc'
    # PLA discards the saved status while keeping the return stack balanced.
    bad_flags.write_bytes(original.replace(read_restore, read_restore[:-1] + b'\x68'))
    result = subprocess.run(command + ['--rom', str(bad_flags)], capture_output=True, text=True, timeout=30)
    if not result.returncode or 'WRAM status=ee, adapter case=15' not in result.stderr:
        raise RuntimeError('Missing bulk read flags restore did not fail assertion 15')
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
    if original.count(guard) != 72:
        raise RuntimeError('Expected four generated I/O guards and five bulk helper guards per runtime bank')
    for label, replacement in (
            ('nmi-depth', bytes.fromhex('a900ea0d831cd00a')),
            ('bank-depth', bytes.fromhex('ad0a1ceaeaead00a'))):
        mutant = out/f'missing-{label}-guard.sfc'
        mutant.write_bytes(original.replace(guard, replacement))
        result = subprocess.run(command + ['--rom', str(mutant)], capture_output=True, text=True, timeout=30)
        if not result.returncode or 'WRAM status=ee, adapter case=10' not in result.stderr:
            raise RuntimeError(f'Missing {label} guard did not fail hardware NMI assertion 10')
    print('Generated I/O stub preserves registers and masks NMI; either missing guard fails case 10.')
    # The general dispatcher can also JMP here when its branch grows long.
    # Bind the mutation to the specialized entry's DP setup, not every JMP.
    fast_prefix = bytes.fromhex('a91beba9005b')
    fast_write = fast_prefix + b'\x4c' + symbols['ppu_write_data'].to_bytes(2, 'little')
    if original.count(fast_write) != 8:
        raise RuntimeError('Expected one fast PPUDATA entry jump per runtime bank')
    skipped = out/'missing-fast-write.sfc'
    skipped.write_bytes(original.replace(fast_write, fast_prefix + plain))
    result = subprocess.run(command + ['--rom', str(skipped)], capture_output=True, text=True, timeout=30)
    if not result.returncode or 'WRAM status=ee, adapter case=10' not in result.stderr:
        raise RuntimeError('Skipped fast PPU write did not fail data/dirty-state assertion 10')
    print('Fast PPUDATA writes/increments/dirties correctly; skipped write fails case 10.')
    blank_defer = bytes.fromhex('a9018da01c4c') + symbols['done'].to_bytes(2, 'little')
    if original.count(blank_defer) != 8:
        raise RuntimeError('Expected one rendering-off producer deferral per bank')
    early_prepare = out/'prepare-while-blanking.sfc'
    early_prepare.write_bytes(original.replace(blank_defer,
        blank_defer[:-2] + symbols['@mask_schedule'].to_bytes(2, 'little')))
    result = subprocess.run(command + ['--rom', str(early_prepare)], capture_output=True, text=True, timeout=30)
    if not result.returncode or 'WRAM status=ee, adapter case=11' not in result.stderr:
        raise RuntimeError('Premature blanking preparation did not fail case 11')
    unchanged = b'\x20' + symbols['ppu_pointer'].to_bytes(2, 'little') + bytes.fromhex('a522c700f0058700')
    # Bulk and general writers share this sequence, once each per bank.
    if original.count(unchanged) != 16:
        raise RuntimeError('Expected bulk and general unchanged-byte guards')
    general = symbols['ppu_write_data']
    redundant = bytearray(original)
    for bank in range(1, 9):
        offset = bank * 65536 + general + 7
        if redundant[offset:offset+2] != b'\xF0\x05':
            raise RuntimeError('General unchanged-byte branch moved')
        redundant[offset:offset+2] = b'\xEA\xEA'
    bad_unchanged = out/'redundant-general-dirty.sfc'
    bad_unchanged.write_bytes(redundant)
    result = subprocess.run(command + ['--rom', str(bad_unchanged)], capture_output=True, text=True, timeout=30)
    if not result.returncode or 'WRAM status=ee, adapter case=24' not in result.stderr:
        raise RuntimeError('Redundant general dirty work did not fail case 24')
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
