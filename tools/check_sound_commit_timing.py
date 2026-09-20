"""Matched-state original/fused sound-helper elapsed master clocks."""
import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
from tools.check_sound_commit import case
from tools.benchmark_report import sha


def run(core, observer, out):
    out.mkdir(parents=True, exist_ok=False)
    matrix = [(0x40, v, 0x30, 15, 0, 0, x, y, mute)
              for x, mute in ((0, 0), (0, 128), (4, 0))
              for y in range(32) for v in (0, 255)]
    folder = out / 'fixture'
    normal = case(core, folder, matrix)
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
    if len(rows) != len(matrix) * 4:
        raise ValueError('Incomplete timing cases')
    samples = []
    for i, row in enumerate(matrix):
        group = rows[i*4:i*4+4]
        if any(len(r) != 16 or int(r[0]) != j or r[5] != points[j] for j, r in enumerate(group)):
            raise ValueError('Timing boundary differs')
        clocks = [int(r[4]) for r in group]
        legacy, fused = clocks[1]-clocks[0], clocks[3]-clocks[2]
        _, value, _, _, _, _, channel, register, mute = row
        suppressed = channel < 4 and mute != 0
        pointer = register if channel < 4 else register & 15
        kind = 'muted' if suppressed else 'channel' if pointer < 16 else 'enable' if pointer == 21 else 'fallback'
        samples.append(dict(channel=channel, register=register, mute=mute, value=value, kind=kind,
            legacy_clocks=legacy, fused_clocks=fused, saved_clocks=legacy-fused))
    groups = {kind: [s['saved_clocks'] for s in samples if s['kind'] == kind]
              for kind in ('channel', 'enable', 'fallback', 'muted')}
    ranges = {k: [min(v), max(v)] for k, v in groups.items()}
    report = dict(passed=all(s['saved_clocks'] > 0 for s in samples if s['kind'] in ('channel', 'enable')),
        samples=samples, savings_by_path=ranges, normal=normal, observer_neutral=True,
        core_sha256=sha(core), observer_sha256=sha(observer),
        sources={str(p): sha(p) for p in [Path(__file__), Path('tools/check_sound_commit.py'),
            Path('tools/build_native.py'), Path('snes/sound_commit.inc'), Path('snes/direct_apu.inc'),
            Path('snes/direct_apu_test.asm'), out / 'spans.csv', out / 'observed.json',
            folder / 'test.lbl', folder / 'runtime.lbl']},
        scope='Matched JSR-through-RTS costs versus original helper using parent direct-APU path. '
        'Full WRAM observer-neutral. Retains muted/fallback overhead. Elapsed costs include '
        'refresh/events; not whole-game speed or hardware interrupt certification.')
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(passed=report['passed'], samples=len(samples), savings_by_path=ranges)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('core', 'observer', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    run(**vars(p.parse_args()))
