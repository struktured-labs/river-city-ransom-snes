"""Actual VRAM and queue-ownership oracle for guarded two-row direct DMA."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import itertools
import json
from pathlib import Path
from tools.check_hidden_high_cache import case, ROOT
from tools.benchmark_report import sha


def run(core, out, full=False):
    out.mkdir(parents=True, exist_ok=False)
    files = [Path(__file__), ROOT/'tools/check_hidden_high_cache.py', ROOT/'tools/check_rows.py']
    files += [ROOT/'snes'/n for n in ('hidden_direct_rows.inc', 'native_prepare.asm',
        'hidden_high_cache_test.asm', 'hidden_direct_probe_setup.inc', 'hidden_direct_probe_readback.inc')]
    hashes = {str(p): sha(p) for p in files}
    starts = range(128) if full else (0, 1, 2, 28, 29, 30, 31, 32, 60, 63, 64, 92, 95, 96, 124, 127)
    matrix = list(itertools.product(starts, (0, 1), (0, 16), (1, 2, 12, 16), (1, 2), (False, True)))
    def execute(item):
        i, (start, mirror, half, budget, calls, dirty_alias) = item
        return case(core, out/f'case-{i:04d}', start=start, mirror=mirror, half=half, budget=budget,
                    calls=calls, dirty_alias=dirty_alias, direct_pair=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(execute, enumerate(matrix)))
    mutants = []
    for name, options, old, new in (
        ('wrong-quadrant-pair', dict(start=1), '    and #1\n    bne @single', '    and #0\n    bne @single'),
        ('budget-overrun', dict(budget=1), '    cmp #2\n    bcc @single\n    lda $1C6C',
             '    cmp #0\n    bcc @single\n    lda $1C6C'),
        ('missing-high-duplicate', {}, '    lda #31\n    mvn', '    lda #15\n    mvn'),
        ('wrong-byte-count', {}, '    lda #64\n    sta $24', '    lda #32\n    sta $24'),
        ('missing-extra-budget', {}, '    dec $1C6B\n    dec $1C6C', '    nop\n    nop\n    nop\n    dec $1C6C'),
        ('mixed-alias-overwrite', dict(start=1,dirty_alias=False),
             '    cmp #1\n    beq @single\n    lda $1D01,x',
             '    cmp #1\n    beq @paired\n    lda $1D01,x')):
        args = dict(budget=12, dirty_alias=True, direct_pair=True)
        args.update(options)
        try:
            case(core, out/name, **args, mutation=('hidden_direct_rows.inc', old, new))
        except ValueError as error:
            mutants.append(dict(name=name, error=str(error)))
        else:
            raise ValueError('Unsafe pair mutant survived: '+name)
    if hashes != {str(p): sha(p) for p in files}:
        raise ValueError('Sources changed during matrix')
    report = dict(passed=True, cases=results, mutants=mutants, sources=hashes, core_sha256=sha(core),
        scope='Full actual 8192-byte tilemap VRAM, source and immutable staging, all flags/requirements, cursor and both budgets. '
        'Every starting row in full mode, both mirroring and pattern modes, mixed and all-dirty aliases, '
        'budgets 1/2/12/16 and changed repeated calls. Not full-game timing or physical audio certification.')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(passed=True, cases=len(results), mutants=len(mutants))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('core', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--full', action='store_true')
    run(**vars(p.parse_args()))
