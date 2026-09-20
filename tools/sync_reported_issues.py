"""Idempotently backfill explicitly requested GitHub reports; dry-run by default."""
import argparse
import json
from pathlib import Path
import subprocess

REPO = 'struktured-labs/river-city-ransom-snes'


def gh(*args):
    return subprocess.check_output(['gh', *args], text=True).strip()


def sync(spec, apply=False):
    wanted = json.loads(spec.read_text())
    existing = json.loads(gh('issue', 'list', '--repo', REPO, '--state', 'all', '--limit', '1000',
                            '--json', 'number,title,state,url'))
    by_title = {r['title']: r for r in existing}
    if len({r['title'] for r in wanted}) != len(wanted): raise ValueError('Duplicate requested titles')
    results = []
    for item in wanted:
        match = by_title.get(item['title'])
        if match:
            results.append(dict(key=item['key'], action='existing', **match))
        elif apply:
            url = gh('issue', 'create', '--repo', REPO, '--title', item['title'], '--body', item['body'])
            result = json.loads(gh('issue', 'view', url, '--repo', REPO, '--json', 'number,title,state,url'))
            if result['title'] != item['title']: raise ValueError('Created issue identity mismatch')
            by_title[item['title']] = result
            results.append(dict(key=item['key'], action='created', **result))
        else:
            results.append(dict(key=item['key'], action='would_create', title=item['title']))
        # Emit each confirmed result, so interruption cannot hide already-created issues.
        print(json.dumps(results[-1]), flush=True)
    return results


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--spec', type=Path, default=Path('docs/reported-issues.json'))
    p.add_argument('--apply', action='store_true')
    a = p.parse_args(); sync(a.spec, a.apply)
