"""Matched-state exact-clock legacy/direct sound-write call measurements."""
import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
from tools.check_direct_apu import case
from tools.benchmark_report import sha


def run(core, observer, out):
    out.mkdir(parents=True, exist_ok=False)
    addresses = list(range(0x4000, 0x4010)) + [0x4015, 0x4010, 0x4017, 0x4018]
    values = [0, 1, 127, 255]
    folder = out / 'fixture'
    normal = case(core, folder, addresses, values)
    labels = {r.split()[2].lstrip('.'): int(r.split()[1], 16)
              for r in (folder / 'test.lbl').read_text().splitlines()}
    points = [f'c3{labels[k]:04x}' for k in ('legacy_call', 'legacy_done', 'fast_call', 'fast_done')]
    env = {k: v for k, v in os.environ.items() if not k.startswith('RCR_')}
    env.update(RCR_SPAN_TRACE=str(out / 'spans.csv'), RCR_PROFILE_FIRST='0', RCR_PROFILE_LAST='360',
               **{f'RCR_SPAN_PC{i}': v for i, v in enumerate(points)})
    subprocess.run([sys.executable, 'tools/smoke_libretro.py', '--core', str(observer), '--rom',
        str(folder / 'test.sfc'), '--kind', 'adapter', '--frames', '360', '--ram', str(out / 'observed.ram'),
        '--receipt', str(out / 'observed.json')], env=env, capture_output=True, check=True, timeout=30)
    if sha(out / 'observed.ram') != normal['ram_sha256']:
        raise ValueError('Timing observer changed execution')
    with (out / 'spans.csv').open() as stream:
        rows = list(csv.reader(stream))
    if len(rows) != len(addresses) * len(values) * 4:
        raise ValueError('Incomplete timing cases')
    samples = []
    for i, (address, value) in enumerate((a, v) for a in addresses for v in values):
        group = rows[i*4:i*4+4]
        if any(len(r) != 16 or int(r[0]) != j or r[5] != points[j] for j, r in enumerate(group)):
            raise ValueError('Timing boundary differs')
        clocks = [int(r[4]) for r in group]
        legacy, direct = clocks[1]-clocks[0], clocks[3]-clocks[2]
        samples.append(dict(address=address, value=value, legacy_clocks=legacy, direct_clocks=direct,
            saved_clocks=legacy-direct, accelerated=address < 0x4010 or address == 0x4015))
    report = dict(passed=all(s['saved_clocks'] > 0 for s in samples if s['accelerated']), samples=samples,
        normal=normal, observer_neutral=True, core_sha256=sha(core), observer_sha256=sha(observer),
        sources={str(p): sha(p) for p in [Path(__file__), Path('tools/check_direct_apu.py'),
            Path('tools/build_native.py'), Path('snes/direct_apu.inc'), Path('snes/direct_apu_test.asm'),
            out / 'spans.csv', out / 'observed.json', folder / 'test.lbl', folder / 'runtime.lbl']},
        scope='Same input and initial APU/caller state, exact JSR-through-RTS costs. All records match '
        'legacy execution and independent oracle. Generic fallback overhead is retained. '
        'Elapsed clocks include refresh/HDMA events, not exclusive instruction costs or gameplay speed.')
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(passed=report['passed'], samples=len(samples),
        fast_savings=[min(s['saved_clocks'] for s in samples if s['accelerated']),
                      max(s['saved_clocks'] for s in samples if s['accelerated'])])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('core', 'observer', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    run(**vars(p.parse_args()))
