"""Bounded metadata-only uprobes of exact running DeckLink/OBS audio callbacks.

No PCM, source settings, recorder, controller or code patches. Uprobes add host
overhead and can affect lock timing; this is not an observer-neutrality claim.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

from tools.benchmark_report import sha

EXPECTED = {
    '/usr/local/lib/libobs.so.30': '94f08a8eef7f563ec32829002b56165ac1c16569c075c03bdfa09d62b1d600b6',
    '/usr/local/lib/obs-plugins/decklink.so': '5a61dc6133c93a7d48a67771c763dce81f39f10e022fe333b7f2e4e572bd7857',
}


def capture(pid, seconds, out):
    if not 1 <= seconds <= 40 or pid <= 1 or out.exists():
        raise ValueError('Need live explicit PID, fresh path and bounded duration')
    proc = Path('/proc')/str(pid)
    if (proc/'exe').resolve() != Path('/usr/local/bin/obs'):
        raise ValueError('Target is not installed OBS')
    maps = (proc/'maps').read_text()
    for path, digest in EXPECTED.items():
        if path not in maps or sha(Path(path)) != digest:
            raise ValueError('Unexpected OBS mapping or instruction bytes')
    start_identity = (proc/'stat').read_text().split()[21]
    source = Path('tools/obs_monitor_packets.bt')
    paths = [Path(__file__), source, Path('/usr/local/bin/obs'),
             Path('/usr/local/include/obs/obs.h'), Path('/usr/local/include/obs/media-io/audio-io.h'),
             Path('/usr/local/include/obs/media-io/media-io-defs.h'), *map(Path, EXPECTED)]
    sources = {str(p): sha(p) for p in paths}
    out.mkdir(parents=True, exist_ok=False)
    command = ['sudo', '-n', 'bpftrace', '-q', '-p', str(pid), str(source), str(pid), str(seconds)]
    report = dict(pid=pid, process_start_ticks=start_identity, seconds_requested=seconds,
                  started_utc=datetime.now(timezone.utc).isoformat(), command=command,
                  sources=sources, scope=__doc__, observer_neutral_verified=False)
    with (out/'packets.csv').open('x') as trace, (out/'stderr.txt').open('x') as errors:
        result = subprocess.run(command, stdout=trace, stderr=errors, timeout=seconds+20)
    report.update(returncode=result.returncode, finished_utc=datetime.now(timezone.utc).isoformat(),
                  same_obs_process=(proc/'stat').read_text().split()[21] == start_identity,
                  sources_unchanged=sources == {str(p): sha(p) for p in paths},
                  artifacts={p.name: sha(p) for p in out.iterdir()})
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report))
    if result.returncode or not report['same_obs_process'] or not report['sources_unchanged']:
        raise ValueError('Observer failed; diagnostic retained')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--seconds', type=int, required=True)
    parser.add_argument('--out', type=Path, required=True)
    capture(**vars(parser.parse_args()))
