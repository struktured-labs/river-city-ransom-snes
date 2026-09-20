"""Execute the native C51B graphics-command consumer and a pointer mutation."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

try:
    from .build_runtime_test import ROOT, build
except ImportError:
    from build_runtime_test import ROOT, build


def check(core, out, pointer_cache=False):
    build(out, native_ring_consumer=True, ring_pointer_cache=pointer_cache)
    command = [sys.executable, str(ROOT/'tools/smoke_libretro.py'),
               '--core', str(core), '--kind', 'adapter', '--frames', '300']
    good = out/'adapter-test.sfc'
    subprocess.run(command + ['--rom', str(good), '--receipt', str(out/'receipt.json')],
                   check=True, capture_output=True, text=True, timeout=30)
    image = good.read_bytes()
    pointer_store = bytes.fromhex('8eb606')
    if image.count(pointer_store) != 16:
        raise RuntimeError('Expected two native consumer read-pointer stores in each bank')
    bad = out/'missing-consumer-read-pointer.sfc'
    bad.write_bytes(image.replace(pointer_store, bytes.fromhex('eaeaea')))
    result = subprocess.run(command + ['--rom', str(bad)], capture_output=True,
                            text=True, timeout=30)
    if not result.returncode or 'WRAM status=ee, adapter case=32' not in result.stderr:
        raise RuntimeError('Missing consumer read-pointer update did not fail case 32')
    controls=[dict(name='read-pointer',rom_sha256=hashlib.sha256(bad.read_bytes()).hexdigest(),
                   expected_case=32,returncode=result.returncode)]
    (out/'read-pointer-negative.log').write_text(result.stdout+result.stderr)
    symbols={line.split()[2].lstrip('.'):int(line.split()[1],16)
             for line in (out/'runtime.lbl').read_text().splitlines()}
    # Deliberately drain four writes during a fade: the following read would
    # mutate the palette eligibility flag, which the one-write budget forbids.
    budget=bytearray(image)
    budget_needle=bytes.fromhex('a001ad3e002902d002a004')
    for bank in range(1,9):
        start=bank*65536+symbols['native_ring_consumer']
        end=bank*65536+symbols['bank_switch_enter']
        if image[start:end].count(budget_needle)!=1:raise RuntimeError('Ambiguous fade budget')
        offset=start+image[start:end].index(budget_needle)+1
        budget[offset]=4
    bad_budget=out/'wrong-fade-budget.sfc';bad_budget.write_bytes(budget)
    result=subprocess.run(command+['--rom',str(bad_budget)],capture_output=True,text=True,timeout=30)
    if not result.returncode or 'WRAM status=ee, adapter case=40' not in result.stderr:
        raise RuntimeError('Extra fade command did not expose the following read at case 40')
    controls.append(dict(name='fade-budget',rom_sha256=hashlib.sha256(budget).hexdigest(),
                         expected_case=40,returncode=result.returncode))
    (out/'fade-budget-negative.log').write_text(result.stdout+result.stderr)
    guarded=bytearray(image)
    needle=bytes.fromhex('ad0a1c0d831cd0')
    for bank in range(1,9):
        start=bank*65536+symbols['native_ring_consumer']
        end=bank*65536+symbols['bank_switch_enter']
        block=image[start:end]
        if block.count(needle)!=1:
            raise RuntimeError('Cannot identify one consumer interrupt guard per bank')
        offset=start+block.index(needle)+6
        guarded[offset:offset+2]=b'\xea\xea'
    bad_guard=out/'missing-consumer-interrupt-guard.sfc'
    bad_guard.write_bytes(guarded)
    result=subprocess.run(command+['--rom',str(bad_guard)],capture_output=True,text=True,timeout=30)
    if not result.returncode or 'WRAM status=ee, adapter case=37' not in result.stderr:
        raise RuntimeError('Missing NMI guard did not fail real-VBlank case 37')
    controls.append(dict(name='nmi-guard',rom_sha256=hashlib.sha256(guarded).hexdigest(),
                         expected_case=37,returncode=result.returncode))
    (out/'nmi-guard-negative.log').write_text(result.stdout+result.stderr)
    bank_guard=bytearray(image)
    for bank in range(1,9):
        start=bank*65536+symbols['native_ring_consumer']
        end=bank*65536+symbols['bank_switch_enter']
        offset=start+image[start:end].index(needle)+3
        # OR NMI depth twice: retain that guard but ignore bank-pair depth.
        bank_guard[offset:offset+3]=bytes.fromhex('0d0a1c')
    bad_bank=out/'missing-consumer-bank-guard.sfc'
    bad_bank.write_bytes(bank_guard)
    result=subprocess.run(command+['--rom',str(bad_bank)],capture_output=True,text=True,timeout=30)
    if not result.returncode or 'WRAM status=ee, adapter case=38' not in result.stderr:
        raise RuntimeError('Missing bank guard did not fail real-VBlank case 38')
    controls.append(dict(name='bank-guard',rom_sha256=hashlib.sha256(bank_guard).hexdigest(),
                         expected_case=38,returncode=result.returncode))
    (out/'bank-guard-negative.log').write_text(result.stdout+result.stderr)
    (out/'report.json').write_text(json.dumps(dict(passed=True,pointer_cache=pointer_cache,
        controls=controls,positive_receipt_sha256=hashlib.sha256((out/'receipt.json').read_bytes()).hexdigest(),
        checker_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),indent=2)+'\n')
    print('Native command budgets, ring wrap, buffered read and ABI pass; '
          'missing pointer updates fail case 32; missing NMI/bank guards fail cases 37/38.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', type=Path, required=True)
    parser.add_argument('--out', type=Path,
                        default=ROOT/'build/native-ring-consumer-oracle')
    parser.add_argument('--pointer-cache',action='store_true')
    args = parser.parse_args()
    check(args.core, args.out,args.pointer_cache)
