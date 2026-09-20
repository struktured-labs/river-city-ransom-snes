"""Execute compact game-engine state equivalence and receiver/timer checks."""
import argparse
from collections import Counter
import json
from pathlib import Path

from tools.benchmark_report import sha
from tools.build_compact_startup_pitch import patch, FLUSH, STAGE
from tools.check_inline_pitch_trial import cases
from tools.check_receiver_poll_trial import stream
from tools.check_startup_pitch_state import state_hash
from tools.check_sweep_driver import Driver


def execute(core, engine, layout, flush, selected):
    local = dict(layout, driver=dict(layout['driver'], startup_flush=flush))
    run = Driver(core, engine, local)
    result = []
    for dp in selected:
        run.seed(dp); before = run.out[384]
        run.call('publish'); run.call('startup_flush')
        result.append((state_hash(run.out), run.out[384]-before,
                       (run.out[0xf2], run.out[0xf3])))
    return result


def check(core, parent, candidate, out):
    if out.exists():
        raise ValueError('Fresh qualification required')
    engines = []
    for root in (parent, candidate):
        meta = json.loads((root/'manifest.json').read_text())
        image = (root/'native-cpu.sfc').read_bytes()
        if sha(root/'native-cpu.sfc') != meta['rom_sha256']:
            raise ValueError('Unbound cartridge')
        at = meta['sweep_driver_rom_offset']
        engines.append(image[at:at+meta['sweep_driver_layout']['engine_bytes']])
    layout = meta['sweep_driver_layout']
    expected, detail = patch(engines[0], layout)
    if expected != engines[1]:
        raise ValueError('Game is not exact compact patch')
    selected = []
    for dp in cases():
        for mask in range(4):
            item = bytearray(dp); item[0x54] = mask; selected.append(item)
    before = execute(core, engines[0], layout, 0x2f80, selected)
    after = execute(core, engines[1], layout, FLUSH, selected)
    errors = [i for i, (a, b) in enumerate(zip(before, after)) if a[0] != b[0]]
    costs = {str(mask): dict(Counter(b[1]-a[1] for dp, a, b in zip(selected, before, after) if dp[0x54] == mask))
             for mask in range(4)}
    bad = bytearray(engines[1])
    for address in STAGE:
        at = address-0x400+9
        if bad[at] != 0xcc:
            raise ValueError('Staged high-byte mutation site changed')
        bad[at] = 0xc9
    subset = [dp for dp in selected if dp[0x54] == 3 and dp[0x55] and dp[0x41] == 8]
    good = execute(core, engines[0], layout, 0x2f80, subset)
    wrong = execute(core, bytes(bad), layout, FLUSH, subset)
    failures = sum(a[0] != b[0] for a, b in zip(good, wrong))
    continuous = {name: [stream(core, engine, layout, mode, delay)
                        for mode in (0, 128) for delay in (0, 256, 512, 2048)]
                  for name, engine in zip(('parent', 'compact'), engines)}
    passed = not errors and failures > 0 and all(
        r['passed'] and not r['bad_volume_writes'] for rows in continuous.values() for r in rows)
    paths = [Path(__file__), Path('tools/build_compact_startup_pitch.py'),
             Path('tools/check_inline_pitch_trial.py'), Path('tools/check_startup_pitch_state.py'),
             Path('tools/check_receiver_poll_trial.py'), Path('tools/check_sweep_driver.py'),
             Path('tools/spc_sweep_driver_probe.inc'), core]
    paths += [root/name for root in (parent, candidate) for name in ('manifest.json', 'native-cpu.sfc')]
    paths += [core.parent.parent/'apu/bapu/smp'/name for name in ('core.cpp', 'smp.cpp', 'memory.cpp', 'timing.cpp')]
    report = dict(passed=passed, cases=len(selected), errors=errors,
        added_clocks_by_pending_mask=costs, different_mmio_shadows=sum(a[2] != b[2] for a, b in zip(before, after)),
        permitted_snapshot_differences=[0xf2, 0xf3], mutant_cases=len(subset), mutant_failures=failures,
        continuous=continuous, sources={str(p): sha(p) for p in paths},
        scope='Actual compact game engine; all final DSP registers and DP bytes except DSP MMIO shadowsF2/F3. '
              'Real publisher/flush, timer and paired receiver execution; not a CPU-register ABI or full-game speed proof.')
    out.mkdir(); (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('sources', 'continuous', 'errors')}))
    if not passed:
        raise ValueError('Compact state/timer qualification failed')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('core', 'parent', 'candidate', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    check(**vars(p.parse_args()))
