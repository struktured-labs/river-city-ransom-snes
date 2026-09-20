"""Measure complete PPU stubs from entry through real RTS/coroutine return."""
import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import sys

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_retained_producer_guard import symbols


def audit(oracle, core, out):
    if out.exists() or any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Fresh isolated execution required')
    proof = bound_report(oracle/'report.json')
    if not proof['passed']:
        raise ValueError('Unqualified oracle')
    out.mkdir(parents=True)
    results, sources = [], dict(proof['sources'])
    # Both latch states and changed/unchanged CHR state, for every actual stub.
    indexes = [i for i, r in enumerate(proof['cases']) if i % 24 in (0, 1)]
    for index in indexes:
        record = proof['cases'][index]
        case, arms = record['case'], {}
        for arm in ('before', 'after'):
            fixture = oracle/f'case-{index:03}'/arm
            rom, labels = fixture/'test.sfc', fixture/'test.lbl'
            for p in (rom, labels):
                if record['artifacts'].get(str(p)) != sha(p):
                    raise ValueError('Changed fixture')
                sources[str(p)] = sha(p)
            after = symbols(labels)['after']
            for observed in (False, True):
                folder = out/f'{index}-{arm}-{observed}'
                folder.mkdir()
                env = os.environ.copy()
                trace = folder/'instructions.csv'
                if observed:
                    env.update(RCR_INSTRUCTION_TRACE=str(trace.resolve()),
                               RCR_PROFILE_FIRST='1', RCR_PROFILE_LAST='6')
                run = subprocess.run([sys.executable, '-m', 'tools.smoke_libretro',
                    '--core', str(core), '--rom', str(rom), '--kind', 'adapter',
                    '--frames', '120', '--ram', str(folder/'memory.ram'),
                    '--receipt', str(folder/'receipt.json')], env=env,
                    capture_output=True, text=True, timeout=30)
                (folder/'execution.log').write_text(run.stdout+run.stderr)
                run.check_returncode()
                if not observed:
                    normal = (folder/'memory.ram').read_bytes()
                    continue
                if normal != (folder/'memory.ram').read_bytes():
                    raise ValueError('Observer changed complete fixture RAM')
                with trace.open() as stream:
                    rows = list(csv.reader(stream))
                starts = [i for i,r in enumerate(rows)
                          if int(r[4],16) == case['BANK']*65536+case['STUB']]
                if len(starts) != 1:
                    raise ValueError('Missing/ambiguous stub invocation')
                start = starts[0]
                ends = [i for i in range(start+1,len(rows))
                        if int(rows[i][4],16) == case['BANK']*65536+after]
                if len(ends) != 1:
                    raise ValueError('Missing/ambiguous real return')
                end = ends[0]
                arms[arm] = dict(entry=rows[start], after_return=rows[end],
                    clocks=int(rows[end][3])-int(rows[start][3]), instructions=end-start)
        results.append(dict(case=case, arms=arms,
            saved_clocks=arms['before']['clocks']-arms['after']['clocks']))
    paths = [Path(__file__), oracle/'report.json', core,
             Path('tools/smoke_libretro.py'), Path('tools/snes9x_instruction_trace.inc'),
             Path('.deps/snes9x/cpuexec.cpp')]
    sources.update({str(p):sha(p) for p in paths})
    report = dict(cases=results, observer_neutral=True, sources=sources,
        artifacts={str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()},
        scope=__doc__+' Masked active-display cases; excludes beam-wait-dependent costs.',
        release_ready=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps([dict(stub=r['case']['STUB'], latch=r['case']['LATCH'],
        before=r['arms']['before']['clocks'], after=r['arms']['after']['clocks'],
        saved=r['saved_clocks']) for r in results]))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('oracle', 'core', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    audit(**vars(p.parse_args()))
