"""Bounded exact-binary producer/mixer-buffer observation; scheduling is perturbed."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

from tools.benchmark_report import sha
from tools.capture_obs_monitor_packets import EXPECTED


def capture(pid, seconds, out):
    if pid <= 1 or not 1 <= seconds <= 40 or out.exists():
        raise ValueError('Need explicit PID, bounded duration and fresh output')
    proc = Path('/proc')/str(pid)
    if (proc/'exe').resolve() != Path('/usr/local/bin/obs'):
        raise ValueError('Unexpected process')
    mappings = (proc/'maps').read_text()
    for path, digest in EXPECTED.items():
        if path not in mappings or sha(Path(path)) != digest:
            raise ValueError('Unexpected probe binary')
    identity = (proc/'stat').read_text().split()[21]
    source = Path('tools/obs_record_buffer.bt')
    paths = [Path(__file__), source, Path('tools/capture_obs_monitor_packets.py'),
             Path('tools/benchmark_report.py'), *map(Path, EXPECTED)]
    sources = {str(p): sha(p) for p in paths}
    out.mkdir(parents=True, exist_ok=False)
    command = ['sudo', '-n', 'bpftrace', '-q', '-p', str(pid), str(source), str(pid), str(seconds)]
    report = dict(pid=pid, process_start_ticks=identity, command=command,
        seconds_requested=seconds, sources=sources, observer_neutral_verified=False,
        started_utc=datetime.now(timezone.utc).isoformat())
    with (out/'packets.csv').open('x') as trace, (out/'stderr.txt').open('x') as err:
        process = subprocess.Popen(command, stdout=trace, stderr=err, start_new_session=True)
        try:
            report['returncode'] = process.wait(timeout=seconds+15)
        except subprocess.TimeoutExpired:
            # Own process group only; root tracer must not survive a failed deadline.
            subprocess.run(['sudo', '-n', 'kill', '-TERM', '--', '-'+str(process.pid)],
                           check=True, timeout=5)
            report['returncode'] = process.wait(timeout=10)
            report['deadline_failed'] = True
    report.update(finished_utc=datetime.now(timezone.utc).isoformat(),
        same_obs_process=(proc/'stat').read_text().split()[21] == identity,
        sources_unchanged=sources == {str(p): sha(p) for p in paths},
        artifacts={p.name: sha(p) for p in out.iterdir()})
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report))
    if report['returncode'] or report.get('deadline_failed') or not report['same_obs_process'] or not report['sources_unchanged']:
        raise ValueError('Unqualified observation retained')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pid', type=int, required=True)
    p.add_argument('--seconds', type=int, required=True)
    p.add_argument('--out', type=Path, required=True)
    capture(**vars(p.parse_args()))
