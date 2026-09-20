"""Retain all text-window differences after the park audio scheduling change."""
import argparse
from collections import Counter
import json
from pathlib import Path
from tools.audit_boundary_publication import compare
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha


def audit(before, after, out):
    if out.exists():
        raise ValueError('Fresh output required')
    a = bound_report(before / 'publication-state.json')
    b = bound_report(after / 'publication-state.json')
    if not a['observer_neutral'] or not b['observer_neutral'] or a['windows'] != b['windows']:
        raise ValueError('Need matching neutral observations')
    records = []
    sources = {**a['sources'], **b['sources']}
    for frame in a['samples']:
        x = Path(a['samples'][frame]['path']).read_bytes()
        y = Path(b['samples'][frame]['path']).read_bytes()
        changed_source = [i for i in range(0x12000,0x13000) if x[i] != y[i]]
        words = [] if changed_source else compare(x, y)
        for word in words:
            r, c = word['tile_row'], word['tile_column']
            at = 0x3000 + r*64 + c*2
            word.update(prepared_before=x[at:at+2].hex(), prepared_after=y[at:at+2].hex(),
                flag_before=x[0x1d00+r],flag_after=y[0x1d00+r],
                age_before=x[0x1e80+r],age_after=y[0x1e80+r])
        records.append(dict(frame=int(frame),changed_source_addresses=changed_source,words=words))
    counts = dict(Counter(w['verdict'] for r in records for w in r['words']))
    source_changes = [r['frame'] for r in records if r['changed_source_addresses']]
    for p in (Path(__file__),Path('tools/audit_boundary_publication.py'),
              Path('tools/audit_main_display_latency.py'),before/'publication-state.json',after/'publication-state.json'):
        sources[str(p)] = sha(p)
    report = dict(sources=sources,records=records,counts=counts,source_changes=source_changes,
        observer_neutral=True,windows=a['windows'],frames_observed=len(records),
        no_publication_regression=not source_changes and not any(counts.get(k,0) for k in
            ('parent_current','unsupported','neither_current')),
        release_ready=False,scope=__doc__+' Exact frame-end source/prepared/VRAM comparison. '
        'First nametable low tile bytes only; changed source, unsupported words and all frames '
        'are retained. Not scanline proof, full-game graphics or acoustic approval.')
    out.mkdir()
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('counts','source_changes','no_publication_regression')}))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('before','after','out'):
        p.add_argument('--'+k,type=Path,required=True)
    audit(**vars(p.parse_args()))
