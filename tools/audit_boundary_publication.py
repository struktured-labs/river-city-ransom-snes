"""Classify changed visible text-tile publication against equal original PPU shadows."""
import argparse
from collections import Counter
import json
from pathlib import Path
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha


def compare(a, b):
    if len(a) != 196608 or len(b) != 196608:
        raise ValueError('Need full WRAM/VRAM snapshots')
    if a[0x12000:0x13000] != b[0x12000:0x13000]:
        raise ValueError('Original nametable sources differ')
    records = []
    for offset in range(0x4000, 0x4800, 2):
        old = a[0x20000+offset]; new = b[0x20000+offset]
        if old == new:
            continue
        index = (offset-0x4000)//2
        source = a[0x12000+index]
        high_a = a[0x20000+offset+1]; high_b = b[0x20000+offset+1]
        # This comparison only interprets the differing first-nametable text
        # words, not arbitrary CHR-remapped playfield bytes or full scanout.
        supported = index//32 in (2, 25, 26, 27) and high_a == high_b
        verdict = ('trial_current' if new == source else 'parent_current' if old == source
                   else 'neither_current') if supported else 'unsupported'
        records.append(dict(vram_offset=offset, tile_row=index//32, tile_column=index%32,
            source=source, before=old, after=new, high_before=high_a, high_after=high_b,
            verdict=verdict))
    return records


def audit(before, after, visual, out):
    if out.exists():
        raise ValueError('Fresh report required')
    a = bound_report(before / 'publication-state.json')
    b = bound_report(after / 'publication-state.json')
    # This review has one aggregate source map, not per-arm source maps.
    v = json.loads((visual / 'report.json').read_text())
    for path, digest in v['sources'].items():
        if sha(path) != digest:
            raise ValueError('Changed visual-review source: ' + path)
    for path, digest in v['artifacts'].items():
        if sha(visual / path) != digest:
            raise ValueError('Changed visual-review artifact: ' + path)
    if not a['observer_neutral'] or not b['observer_neutral'] or a['windows'] != b['windows']:
        raise ValueError('Missing matching neutral windows')
    sources = {**a['sources'], **b['sources'], **v['sources']}
    for proof, name in [(a, 'before'), (b, 'after')]:
        normal = Path(proof['normal']) / 'capture.json'
        if v['sources'].get(str(normal)) != sha(normal):
            raise ValueError('State run and visual report lack shared control')
        receipt = json.loads((Path(proof['normal']) / 'capture.json').read_text())
        if receipt['rom_sha256'] != v['runs'][name]['rom_sha256']:
            raise ValueError('Wrong state cartridge')
    records = []; source_changes = []
    for frame in a['samples']:
        x = Path(a['samples'][frame]['path']).read_bytes()
        y = Path(b['samples'][frame]['path']).read_bytes()
        changes = [i for i in range(0x12000, 0x13000) if x[i] != y[i]]
        if changes:
            source_changes.append(dict(frame=int(frame), addresses=changes,
                before=[x[i] for i in changes], after=[y[i] for i in changes]))
    for item in v['visual']:
        frame = item['frame']
        x = Path(a['samples'][str(frame)]['path']).read_bytes()
        y = Path(b['samples'][str(frame)]['path']).read_bytes()
        records.append(dict(frame=frame, pixel_delta=item, words=compare(x, y)))
    counts = dict(Counter(w['verdict'] for r in records for w in r['words']))
    unresolved = [r['frame'] for r in records if not r['words'] or
                  any(w['verdict'] in ('unsupported', 'neither_current') for w in r['words'])]
    for p in (Path(__file__), Path('tests/test_boundary_publication.py'),
              before / 'publication-state.json', after / 'publication-state.json', visual / 'report.json'):
        sources[str(p)] = sha(p)
    report = dict(sources=sources, counts=counts, records=records,
        equal_original_shadow_frames=len(a['samples'])-len(source_changes),
        original_shadow_difference_frames=source_changes, unresolved_frames=unresolved,
        no_publication_regression=counts.get('parent_current', 0) == 0 and not unresolved,
        release_ready=False, scope=__doc__ + ' Frame-end WRAM/VRAM is not a per-scanline '
        'render proof. Every changed-picture frame remains represented; unsupported values '
        'and no-word-change frames are unresolved, not successes.')
    out.mkdir(parents=True)
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('counts', 'unresolved_frames', 'no_publication_regression')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('before', 'after', 'visual', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    audit(**vars(parser.parse_args()))
