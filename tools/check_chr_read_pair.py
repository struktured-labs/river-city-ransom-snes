"""Bind four-arm CHR matrices and execute paired-source-read negative controls."""
import argparse
import json
from pathlib import Path

from tools.benchmark_report import sha
from tools.check_chr_read_cache import execute, patch_runtime


def verify_matrix(folder, enabled):
    report = json.loads((folder/'report.json').read_text())
    if not report['passed'] or report['read_pair'] is not enabled or report['positive_cartridges'] != 128:
        raise ValueError('Incomplete or wrong positive matrix')
    for name, digest in report['sources'].items():
        if sha(Path(name)) != digest:
            raise ValueError('Changed matrix input: '+name)
    for row in report['positives']+report['mutants']:
        for name, digest in row['artifacts'].items():
            if sha(Path(name)) != digest:
                raise ValueError('Changed matrix artifact: '+name)
    return report


def run(core, scalar, paired, out):
    a, b = verify_matrix(scalar, False), verify_matrix(paired, True)
    if a['sources'] != b['sources'] or b['sources'][str(core)] != sha(core):
        raise ValueError('Different matrix source/core inputs')
    out.mkdir(parents=True, exist_ok=False)
    base = paired/'cache-1-page-10-mode-00'
    labels = {line.split()[2].lstrip('.'): int(line.split()[1], 16)
              for line in (base/'runtime.lbl').read_text().splitlines()}
    image = (base/'adapter-test.sfc').read_bytes()
    low, high = labels['bulk_source_byte'], labels['bulk_fill_loop']
    region = image[65536+low:65536+high]
    specs = [
        ('missing-lookahead', bytes.fromhex('8524e654a7548d2a1c'), 6, 3, 13),
        ('missing-increment', bytes.fromhex('ee261cee261c'), 0, 3, 13),
        ('ignore-stride', bytes.fromhex('ad201c2904d0'), 5, 2, 13),
        ('ignore-chr-limit', bytes.fromhex('ad271cc920b0'), 5, 2, 15),
        ('ignore-page-boundary', bytes.fromhex('ad261cc9feb0'), 5, 2, 15),
        ('missing-low-pointer', bytes.fromhex('ad261c8554a754'), 3, 2, 13),
    ]
    mutants = []
    for name, pattern, skip, size, failure in specs:
        if region.count(pattern) != 1:
            raise ValueError('Nonunique mutation: '+name)
        offset = region.index(pattern)+skip
        before = region[offset:offset+size]
        folder = out/name
        folder.mkdir()
        rom = folder/'mutant.sfc'
        rom.write_bytes(patch_runtime(image, low+offset, before, b'\xea'*size))
        row = execute(core, rom, folder, expected_failure=failure)
        row.update(name=name, address=low+offset, before=before.hex())
        mutants.append(row)
    # The paired reader now dereferences the persistent pointer directly.
    # Break its shared miss-path stores, not just the generic caller's copy.
    start,end=labels['chr_read_pointer'],labels['ppu_increment']
    resolver=image[65536+start:65536+end]
    for name,pattern,failure in (
        # Both miss-path stores are also consumed by the first public read;
        # the executed diagnostic rejects either corruption in case 2.
        ('missing-cache-high',bytes.fromhex('a5018d551b'),2),
        ('missing-cache-bank',bytes.fromhex('a5028d561b'),2)):
        if resolver.count(pattern)!=1:
            raise ValueError('Nonunique persistent-pointer mutation: '+name)
        address=start+resolver.index(pattern)+2
        folder=out/name
        folder.mkdir()
        rom=folder/'mutant.sfc'
        before=image[65536+address:65536+address+3]
        rom.write_bytes(patch_runtime(image,address,before,b'\xea'*3))
        row=execute(core,rom,folder,expected_failure=failure)
        row.update(name=name,address=address,before=before.hex())
        mutants.append(row)
    report = dict(passed=True, positive_cartridges=256, mutants=mutants,
        sources={str(p): sha(p) for p in (Path(__file__), scalar/'report.json', paired/'report.json', core)},
        scope='Four arms: read pair off/on crossed with cache off/on. All pages, inversion modes, '
              'selected CHR bank values, public reads with increment 1/32, plus adapter ABI and '
              'FD/FE/FF boundary, nametable and swapped palette cases. Eight reader/persistent-pointer mutants '
              'rejected in addition to six cache mutants in each matrix. Not arbitrary decimal '
              'or pending-interrupt states; not a game-speed or acoustic pass.')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(passed=True, positive_cartridges=256, rejected_pair_mutants=len(mutants))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('core', 'scalar', 'paired', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    run(**vars(parser.parse_args()))
