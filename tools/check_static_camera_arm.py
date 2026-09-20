"""Execute full stationary-camera hook readiness and real NMI edge cases."""
import argparse
import json
from pathlib import Path

from tools.benchmark_report import sha
from tools.check_camera_edge import case


READY = dict(task=192, guard=0, pause=0, fade=4, level=4, transition=0)


def run(core, out):
    out.mkdir(parents=True, exist_ok=False)
    paths = [Path(__file__), Path('tools/check_camera_edge.py'), Path('snes/native_runtime.asm'),
             Path('snes/camera_static_ready.inc'), Path('snes/camera_edge_test.asm'),
             Path('snes/camera_publish_safe.inc'), Path('snes/interrupt_policy.inc'),
             Path('snes/wram_clear.inc'), Path('snes/native_boot.cfg'),
             Path('tools/smoke_libretro.py'), core,
             Path('.deps/cc65/bin/ca65'), Path('.deps/cc65/bin/ld65')]
    sources = {str(p): sha(p) for p in paths}
    cases = []
    states = [({}, True), ({'task': 193}, True)]
    states += [({key: value}, False) for key, value in
               (('task', 128), ('guard', 128), ('pause', 32), ('fade', 2),
                ('fade', 128), ('level', 3), ('transition', 1), ('transition', 2))]
    for index, (override, ready) in enumerate(states):
        state = dict(READY, **override)
        for line in (10, 241):
            r = case(core, out/f'state-{index}-line-{line}', line, 0, False, True,
                     safe=True, static_state=state, static_arm=True, expect_armed=ready)
            if r['nmi_count'] != int(ready and line == 241):
                raise ValueError('Wrong fresh-event service count')
            cases.append(r)
    for line, nops, served in ([(239, n, False) for n in (0, 20, 40, 60, 80, 100, 120)]
                              + [(243, 0, True), (250, 0, True)]):
        r = case(core, out/f'edge-{line}-{nops}-{int(served)}', line, nops, served, True,
                 safe=True, static_state=READY, static_arm=True)
        if r['nmi_count'] != 1:
            raise ValueError('Fresh edge lost or acknowledged edge duplicated')
        cases.append(r)
    disabled = case(core, out/'disabled', 241, 0, False, True, safe=True,
                    static_state=READY, expect_armed=False)
    if disabled['nmi_count'] != 0:
        raise ValueError('Old unarmed control did not reproduce')
    mutants = []
    for name, state, mutation in (
        ('ignore-guard', dict(READY, guard=128), ('    bmi @not_ready', '    nop\n    nop')),
        ('ignore-pause', dict(READY, pause=32), ('    and #$20', '    and #0')),
        ('ignore-fade', dict(READY, fade=2), ('    and #$82', '    and #0')),
        ('wrong-level', dict(READY, level=3), ('    cmp #4', '    cmp #3'))):
        try:
            case(core, out/name, 241, 0, False, True, safe=True, static_state=state,
                 static_arm=True, expect_armed=False, mutation=mutation)
        except ValueError as error:
            if str(error) not in ('Camera publication or retained state mismatch',
                                  'Wrong static-camera arming decision'):
                raise
            mutants.append(dict(name=name, rejection=str(error)))
        else:
            raise ValueError('Unsafe arming mutant survived: '+name)
    if sources != {str(p): sha(p) for p in paths}:
        raise ValueError('Static-arm fixture sources changed')
    report = dict(passed=True, cases=cases, disabled_control=disabled, mutants=mutants,
        sources=sources, artifacts={str(p): sha(p) for p in out.rglob('*') if p.is_file()},
        scope='Full extracted camera hook, stationary low/high camera entries, all readiness '
              'guards, caller A/P/X/Y/stack, real visible/fresh/acknowledged NMI edges. '
              'Does not execute the deferred original-game NMI body or certify game timing.')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(passed=True, cases=len(cases), mutants=len(mutants))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('core', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    run(**vars(p.parse_args()))
