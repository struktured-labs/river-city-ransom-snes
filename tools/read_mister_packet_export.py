"""Wait for a complete, stable diagnostic export; retain every rejected snapshot.

Read-only on Rival. Call AFTER an explicitly requested Save Backup RAM. A fresh
minimum total excludes an unchanged older save; repeat exports may instead bind
the exact previously validated digest. Does not establish timing neutrality.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

from tools.audio_packet_log import decode
from tools.benchmark_report import sha

REMOTE = '/media/fat/saves/SNES/RCR-SNES-985f22e5e524.sav'


def validate(data, minimum_total, expected_sha256=None):
    log = decode(data)
    digest = hashlib.sha256(data).hexdigest()
    if log['total'] < minimum_total:
        raise ValueError('Old export: total below required minimum')
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError('Repeated export differs from validated snapshot')
    return dict(total=log['total'], sha256=digest)


def acquire(out, minimum_total, expected_sha256=None, *, reader=None, attempts=20, pause=time.sleep):
    if minimum_total < 1 or not 2 <= attempts <= 40 or out.exists():
        raise ValueError('Need positive minimum, bounded attempts and fresh directory')
    if expected_sha256 is not None and (len(expected_sha256) != 64 or
            any(c not in '0123456789abcdef' for c in expected_sha256)):
        raise ValueError('Expected SHA-256 must be lowercase hex')
    if reader is None:
        def reader():
            return subprocess.check_output(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=3',
                                            'rivalmage', 'cat', REMOTE], timeout=4)
    out.mkdir(parents=True, exist_ok=False)
    report = dict(passed=False, remote=REMOTE, minimum_total=minimum_total,
                  expected_sha256=expected_sha256, snapshots=[], scope=__doc__,
                  sources={str(p): sha(p) for p in (Path(__file__), Path('tools/audio_packet_log.py'))})
    previous = None
    try:
        for index in range(attempts):
            entry = dict(index=index, monotonic=time.monotonic())
            report['snapshots'].append(entry)
            try:
                data = reader()
                path = out/f'snapshot-{index:02}.srm'
                with path.open('xb') as stream:
                    stream.write(data)
                entry.update(file=path.name, sha256=sha(path), size=len(data))
                verified = validate(data, minimum_total, expected_sha256)
                entry.update(valid=True, total=verified['total'])
                if previous == verified['sha256']:
                    report.update(passed=True, accepted_file=path.name, **verified)
                    break
                previous = verified['sha256']
            except (ValueError, subprocess.SubprocessError) as error:
                entry.update(valid=False, error=str(error))
                previous = None
            if index+1 < attempts:
                pause(.25)
    finally:
        report['artifacts'] = {p.name: sha(p) for p in out.glob('*.srm')}
        (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    if not report['passed']:
        raise ValueError('No complete stable export within bounded reads')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--minimum-total', type=int, required=True)
    parser.add_argument('--expected-sha256')
    args = parser.parse_args()
    print(json.dumps(acquire(**vars(args))))
