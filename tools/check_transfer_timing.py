"""Matched isolated SPC transport timing, including VBlank; not gameplay fidelity."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

try:
    from .analyze_spc_ack import analyze
except ImportError:
    from analyze_spc_ack import analyze

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(core, observer, out):
    out.mkdir(parents=True, exist_ok=False)
    reports = {}
    for name, paired in [('single', False), ('paired', True)]:
        for mode, selected in [('normal', core), ('observed', observer)]:
            destination = out / f'{name}-{mode}'
            env = os.environ.copy()
            env.pop('RCR_SPC_ACK_TRACE', None)
            if mode == 'observed':
                env['RCR_SPC_ACK_TRACE'] = str(out / f'{name}.csv')
            code = ("from pathlib import Path; from tools.check_audio import check; "
                    f"assert check(Path({str(selected)!r}), Path({str(destination)!r}), paired={paired!r})")
            run = subprocess.run([sys.executable, '-c', code], cwd=ROOT, env=env,
                                 capture_output=True, text=True)
            (out / f'{name}-{mode}.log').write_text(run.stdout + run.stderr)
            if run.returncode:
                raise RuntimeError(f'{name}-{mode} signal check failed; see log')
        with (out / f'{name}.csv').open() as stream:
            rows = list(csv.reader(stream))
        if not rows or any(len(row) != 9 for row in rows):
            raise ValueError('Timing requires the absolute-clock observer')
        report = analyze(rows, paired=paired)
        report['trace_sha256'] = sha(out / f'{name}.csv')
        report['observer_equal'] = all(
            sha(out / f'{name}-normal' / filename) == sha(out / f'{name}-observed' / filename)
            for filename in ('audio.wav', 'timeline.json', 'script.sfc'))
        (out / f'{name}-audit.json').write_text(json.dumps(report, indent=2) + '\n')
        reports[name] = report
    single, paired = [reports[name]['data_phase_timing'] for name in ('single', 'paired')]
    passed = (all(r['observer_equal'] for r in reports.values())
              and single['measured_packets'] == paired['measured_packets'] > 0
              and single['excluded_packets'] == paired['excluded_packets'] == 0
              and paired['mean_master_clocks'] < single['mean_master_clocks'])
    result = dict(passed=passed, release_ready=False,
                  scope='Matched isolated pulse script; handshake ACK to last byte ACK, not synthesis, full call latency, or game speed',
                  core_sha256=sha(core), observer_sha256=sha(observer),
                  single=single, paired=paired,
                  mean_saving_percent=100*(1-paired['mean_master_clocks']/single['mean_master_clocks']))
    (out / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
    (out / 'index.html').write_text(
        '<!doctype html><meta charset="utf-8"><title>SPC transfer timing</title>'
        '<h1>Isolated single vs paired transport</h1>'
        '<p>All packet data phases, including VBlank. Not a gameplay or popping verdict.</p>'
        '<h2>Single</h2><audio controls src="single-normal/audio.wav"></audio>'
        '<h2>Paired</h2><audio controls src="paired-normal/audio.wav"></audio>'
        '<p><a href="report.json">Timing summary</a> · '
        '<a href="single-audit.json">Single audit</a> · '
        '<a href="paired-audit.json">Paired audit</a></p>')
    print(json.dumps(result, indent=2))
    return passed


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', type=Path, required=True)
    parser.add_argument('--observer', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if check(args.core.resolve(), args.observer.resolve(), args.out.resolve()) else 1)
