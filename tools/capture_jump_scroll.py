"""Input-only, matched jump/scroll episode on original NES and current SNES.

Run each core in a fresh process. Both use logical NES A+B, not a SNES-only
shortcut. The cadence approximates the requested physical episode, not its
unknown exact input-consumption times or encounter state.
"""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path

from tools import benchmark_capture as bench
from tools.benchmark_report import verify_capture

NAME = 'matched-horizontal-jump'


def scenario():
    prefix = bench.SCENARIO[:next(i for i, p in enumerate(bench.SCENARIO) if p['name'] == 'idle')]
    return [dict(p) for p in prefix] + [
        dict(name='jump_idle', frames=60),
        dict(name='jump_right', frames=960, buttons=['Right', 'A', 'B'],
             hold_buttons=['Right'], pulse=[30, 18]),
        dict(name='jump_left', frames=240, buttons=['Left', 'A', 'B'],
             hold_buttons=['Left'], pulse=[30, 18]),
        dict(name='jump_settle', frames=60),
    ]


@contextmanager
def registered():
    # Process-local extension; do not change historical benchmark sources or
    # pretend their hash alone authenticates this additional scenario.
    original = bench.scenario_for
    bench.scenario_for = lambda name: scenario() if name == NAME else original(name)
    try:
        yield
    finally:
        bench.scenario_for = original


def capture(system, core, rom, out):
    if any(k.startswith(('RCR_MAIN_', 'RCR_NES_', 'RCR_RENDER_', 'RCR_SPC_', 'RCR_AUDIO_')) for k in os.environ):
        raise ValueError('Use a clean observer environment')
    paths = [Path(__file__), Path(bench.__file__), Path('tools/smoke_libretro.py'), core, rom]
    before = {str(p): bench.sha(p) for p in paths}
    refs = {'menu': (Path('build/reference-title-05'), 600),
            **{name: (Path('build/reference-walk-02'), frame)
               for name, frame in [('settings', 600), ('story', 900), ('street', 1800)]}}
    with registered():
        bench.capture(core, rom, system, refs, out, NAME, True, True)
        receipt, _ = verify_capture(out)
    if not receipt['capture_complete']:
        raise ValueError('Incomplete episode')
    if before != {str(p): bench.sha(p) for p in paths}:
        raise ValueError('Capture sources changed')
    (out / 'jump-binding.json').write_text(json.dumps(dict(sources=before,
        capture_sha256=bench.sha(out / 'capture.json'), scenario=scenario(),
        scope=__doc__), indent=2) + '\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--system', choices=('nes', 'snes'), required=True)
    for name in ('core', 'rom', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    capture(**vars(p.parse_args()))
