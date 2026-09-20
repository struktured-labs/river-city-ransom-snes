"""Run prefix observer in a child; authenticate trace files after process exit."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from tools.benchmark_report import sha
from tools.audit_main_display_latency import bound_report


def capture(candidate, core, control, out):
    if out.exists():
        raise ValueError('Fresh output required')
    sources = {str(p): sha(p) for p in (Path(__file__), Path('tools/capture_audio_prefix.py'),
                                      candidate / 'native-cpu.sfc', core)}
    started = time.monotonic()
    subprocess.run([sys.executable, '-m', 'tools.capture_audio_prefix', '--candidate', str(candidate),
        '--core', str(core), '--control', str(control), '--out', str(out)], check=True)
    exited = time.monotonic()
    path = out / 'audio-prefix.json'
    report = json.loads(path.read_text())
    traces = set(report['traces'].values())
    finalized = []
    for name, digest in report['sources'].items():
        actual = sha(name)
        if actual != digest:
            if name not in traces:
                raise ValueError('Non-trace source changed: ' + name)
            finalized.append(dict(path=name, pre_exit_sha256=digest, post_exit_sha256=actual))
            report['sources'][name] = actual
    if any(sha(p) != h for p, h in sources.items()):
        raise ValueError('Wrapper source changed')
    # Retain the premature receipt rather than overwriting its claims in place.
    pre_exit = out / 'pre-exit-audio-prefix.json'
    path.rename(pre_exit)
    report['sources'].update(sources)
    report['sources'][str(pre_exit)] = sha(pre_exit)
    report['post_exit_finalization'] = dict(changed_buffered_traces=finalized,
        child_wall_seconds=exited-started, total_wall_seconds=time.monotonic()-started,
        scope='Producer process exited successfully before final trace hashes were taken. '
              'Pre-exit receipt retained as incomplete trace-hash evidence, not a valid cache.')
    path.write_text(json.dumps(report, indent=2) + '\n')
    bound_report(path)
    print(json.dumps(report['post_exit_finalization']))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'core', 'control', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    capture(**vars(parser.parse_args()))
