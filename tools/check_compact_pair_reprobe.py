"""Run the actual relocated paired helper against the independent full VRAM oracle."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import itertools
import json
from pathlib import Path
import subprocess

from tools.benchmark_report import sha
from tools.build_compact_pair_reprobe import HELPER, SIZE
from tools.build_hidden_index_trial import labels
from tools.build_inline_pitch_trial import checksum
from tools.check_hidden_high_cache import case


def inject(image, entry, helper):
    if len(image) != 0x200000 or len(helper) != SIZE:
        raise ValueError('Wrong fixture/helper shape')
    if image[HELPER:HELPER+SIZE] != b'\xff'*SIZE:
        raise ValueError('Fixture overlaps actual helper')
    if image[entry:entry+4] != helper[:4]:
        raise ValueError('Unexpected scalar fixture entry')
    image = bytearray(image)
    image[entry:entry+3] = b'\x4c'+HELPER.to_bytes(2, 'little')
    image[HELPER:HELPER+SIZE] = helper
    checksum(image)
    return image


def mutate(helper, old, new):
    before, after = bytes.fromhex(old), bytes.fromhex(new)
    if len(before) != len(after) or helper.count(before) != 1:
        raise ValueError('Ambiguous or resized binary mutant')
    return helper.replace(before, after)


def run(candidate, core, out, full=False):
    if out.exists():
        raise ValueError('Fresh output required')
    manifest = json.loads((candidate/'manifest.json').read_text())
    image = (candidate/'native-cpu.sfc').read_bytes()
    helper = (candidate/'pair.bin').read_bytes()
    entry = manifest['experimental_compact_pair_reprobe']['old_entry']
    if (sha(candidate/'native-cpu.sfc') != manifest['rom_sha256']
            or image[HELPER:HELPER+SIZE] != helper
            or image[entry:entry+3] != b'\x4c'+HELPER.to_bytes(2, 'little')):
        raise ValueError('Changed production helper/trampoline')
    files = [Path(__file__), Path('tools/build_compact_pair_reprobe.py'),
        Path('tools/build_hidden_index_trial.py'), Path('tools/build_inline_pitch_trial.py'),
        Path('tools/check_hidden_high_cache.py'), Path('tools/check_rows.py'),
        Path('tools/smoke_libretro.py'), core, candidate/'native-cpu.sfc',
        candidate/'pair.bin', candidate/'manifest.json']
    files += [Path('snes')/n for n in ('hidden_direct_rows.inc', 'native_prepare.asm',
        'hidden_high_cache_test.asm', 'hidden_direct_probe_setup.inc',
        'hidden_direct_probe_readback.inc', 'native_boot.cfg', 'wram_clear.inc')]
    sources = {str(p): sha(p) for p in files}
    variants = {
        'wrong-quadrant': mutate(helper, 'a514290100d0', 'a514290000d0'),
        'short-pair': mutate(helper, 'a940008524', 'a920008524'),
        'short-high-copy': mutate(helper, 'a91f00547e7e', 'a90f00547e7e'),
        'missing-extra-budget': mutate(helper, 'ce6b1cce6c1c', 'eaeaeace6c1c'),
    }
    # The existing oracle assembles its scalar fixture normally. Immediately
    # before execution, replace only its helper entry and free C0:D500 bytes
    # with the authenticated production trampoline/helper. No source substitution
    # or relocated reconstruction of the code under test is involved.
    original_run = subprocess.run
    injected = {}
    def execute(command, *args, **kwargs):
        if (isinstance(command, list) and '--kind' in command and '--rom' in command
                and any(str(v).endswith('smoke_libretro.py') for v in command)):
            rom = Path(command[command.index('--rom')+1])
            if not rom.resolve().is_relative_to(out.resolve()):
                raise ValueError('Unexpected fixture outside oracle')
            tag = rom.parent.name
            selected = variants.get(tag, helper)
            site = labels(rom.parent/'test.lbl')['prepare_hidden_direct_row']
            rom.write_bytes(inject(rom.read_bytes(), site, selected))
            injected[tag] = dict(rom_sha256=sha(rom), helper_sha256=__import__('hashlib').sha256(selected).hexdigest(),
                                 entry=site, trampoline=b'\x4c'+HELPER.to_bytes(2, 'little'))
        return original_run(command, *args, **kwargs)
    starts = range(128) if full else (0, 1, 2, 28, 29, 30, 31, 32, 60, 63, 64, 92, 95, 96, 124, 127)
    matrix = list(itertools.product(starts, (0, 1), (0, 16), (1, 2, 15, 16), (1, 2), (False, True)))
    def check(item):
        i, (start, mirror, half, budget, calls, alias) = item
        return case(core, out/f'case-{i:04d}', start=start, mirror=mirror, half=half,
                    budget=budget, calls=calls, dirty_alias=alias, compact_index=True)
    out.mkdir(parents=True)
    subprocess.run = execute
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(check, enumerate(matrix)))
        mutants = []
        for name in variants:
            try:
                case(core, out/name, start=1 if name == 'wrong-quadrant' else 0,
                     budget=15, calls=2, dirty_alias=True, compact_index=True)
            except ValueError as error:
                if not str(error).startswith('Hidden cache '):
                    raise
                mutants.append(dict(name=name, rejection=str(error)))
            else:
                raise ValueError('Executed binary mutant survived: '+name)
    finally:
        subprocess.run = original_run
    if len(injected) != len(results)+len(mutants):
        raise ValueError('Not every fixture executed actual candidate code')
    for name, record in injected.items():
        record['trampoline'] = record['trampoline'].hex()
        folder = out/name
        for filename in ('test.sfc', 'memory.ram', 'receipt.json', 'execution.log'):
            sources[str(folder/filename)] = sha(folder/filename)
    if any(sha(Path(p)) != digest for p, digest in sources.items()):
        raise ValueError('Source changed during oracle')
    result = dict(passed=True, cases=results, mutants=mutants, injected=injected, sources=sources,
        release_ready=False, production_rom_sha256=manifest['rom_sha256'],
        scope='Actual C0:D500 helper bytes plus exact trampoline in scalar native-producer fixtures. '
        'Independent 8192-byte actual VRAM, all row flags/requirements, cursor/budgets, unchanged '
        'shadow/staging. Selected starting rows unless full; both mirror/pattern halves, budgets '
        '1/2/15/16, one/two changed calls, mixed/all-dirty aliases. No injected interrupts, '
        'complete game-state equivalence or physical timing/audio certification.')
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(passed=True, cases=len(results), mutants=len(mutants))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'core', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--full', action='store_true')
    run(**vars(p.parse_args()))
