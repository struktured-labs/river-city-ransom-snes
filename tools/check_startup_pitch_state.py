"""Execute staged-pitch publisher/flush state equivalence and real timer checks."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_startup_pitch_trial import patch, ORIGIN
from tools.check_inline_pitch_trial import cases
from tools.check_receiver_poll_trial import stream
from tools.check_sweep_driver import Driver


def state_hash(snapshot):
    values = list(snapshot[:384])
    # $F2/$F3 are DSP address/data MMIO shadows, not application RAM. A later
    # pitch write legitimately leaves those shadows different from a KON write.
    # Keep every actual DSP register (snapshot256..383) and all other DP bytes.
    values[0xf2] = values[0xf3] = 0
    return hashlib.sha256(bytes(values)).hexdigest()


def run(core, engine, layout, selected):
    layout = dict(layout, driver=dict(layout['driver'], flush=0x2f80))
    driver = Driver(core, engine, layout)
    results = []
    for dp in selected:
        driver.seed(dp)
        before = driver.out[384]
        driver.call('publish')
        driver.call('flush')
        results.append((state_hash(driver.out), driver.out[384]-before,
                        (driver.out[0xf2], driver.out[0xf3])))
    return results


def check(core, candidate, trial, out):
    if out.exists():
        raise ValueError('Fresh state report required')
    game = json.loads((candidate/'manifest.json').read_text())
    layout = game['sweep_driver_layout']
    original = (candidate/'native-cpu.sfc').read_bytes()
    if sha(candidate/'native-cpu.sfc') != game['rom_sha256']:
        raise ValueError('Unbound current engine')
    original = original[game['sweep_driver_rom_offset']:game['sweep_driver_rom_offset']+layout['engine_bytes']]
    baseline, changed, detail = patch(original, layout)
    for name, engine in [('baseline', baseline), ('trial', changed)]:
        bound_report(trial/name/'manifest.json')
        if (trial/name/'engine.bin').read_bytes() != engine:
            raise ValueError('Fixture is not this exact prototype')
    selected = []
    for dp in cases():
        for mask in range(4):
            item = bytearray(dp); item[0x54] = mask; selected.append(item)
    a = run(core, baseline, layout, selected)
    b = run(core, changed, layout, selected)
    mismatches = [i for i, (x, y) in enumerate(zip(a, b)) if x[0] != y[0]]
    costs = {str(mask): dict(Counter(y[1]-x[1] for dp, x, y in zip(selected, a, b) if dp[0x54] == mask))
             for mask in range(4)}
    mutant = bytearray(changed)
    for voice in (0, 1):
        at = detail['labels'][f'stage{voice}']-0x400+12
        if mutant[at] != 0xcc:
            raise ValueError('Wrong staged-high mutation site')
        mutant[at] = 0xc9  # Store low X in the high slot instead of Y.
    subset = [dp for dp in selected if dp[0x54] == 3 and dp[0x55] and dp[0x41] == 8]
    expected = run(core, baseline, layout, subset)
    wrong = run(core, bytes(mutant), layout, subset)
    mutant_failures = sum(x[0] != y[0] for x, y in zip(expected, wrong))
    continuous = {name: [stream(core, engine, layout, mode, delay)
                        for mode in (0, 128) for delay in (0, 256, 512, 2048)]
                  for name, engine in [('baseline', baseline), ('trial', changed)]}
    passed = not mismatches and bool(mutant_failures) and all(
        r['passed'] and not r['bad_volume_writes'] for side in continuous.values() for r in side)
    paths = [Path(__file__), Path('tools/build_startup_pitch_trial.py'),
             Path('tools/check_inline_pitch_trial.py'), Path('tools/check_sweep_driver.py'),
             Path('tools/check_receiver_poll_trial.py'), Path('tools/spc_sweep_driver_probe.inc'),
             core, candidate/'manifest.json', candidate/'native-cpu.sfc']
    paths += [trial/name/file for name in ('baseline', 'trial') for file in ('manifest.json', 'engine.bin')]
    paths += [core.parent.parent/'apu/bapu/smp'/n for n in ('core.cpp', 'smp.cpp', 'memory.cpp', 'timing.cpp')]
    report = dict(passed=passed, cases=len(selected), mismatches=mismatches,
        added_clocks_by_pending_mask=costs, mutant_cases=len(subset), mutant_failures=mutant_failures,
        different_dsp_mmio_shadows=sum(x[2] != y[2] for x, y in zip(a, b)),
        permitted_snapshot_differences=[0xf2, 0xf3],
        continuous=continuous, sources={str(p): sha(p) for p in paths},
        scope='Actual publisher then flush, all11-bit periods, enable/control/envelope cases '
              'and all four pending masks. DP equality except DSP MMIO shadowsF2/F3; all actual '
              'final DSP registers equal. Not CPU register ABI '
              'or internal DSP waveform equality. Appended staging RAM is outside DP and is '
              'checked through its effect on final DSP output, not bytewise RAM equivalence. '
              'Delayed paired-port and idle-timer checks remain separate from game speed.')
    out.mkdir()
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('sources', 'continuous', 'mismatches')}))
    if not passed:
        raise ValueError('Staged pitch state/timer gate failed')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('core', 'candidate', 'trial', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    check(**vars(p.parse_args()))
