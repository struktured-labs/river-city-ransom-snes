"""Input-only combat policies, isolated from historical benchmark definitions.

Fresh processes are required for captures. The temporary dispatcher is also used
when verifying these receipts; it never changes the historical scenario module
on disk or accepts a policy supplied by an untrusted capture manifest.
"""
import argparse
from contextlib import contextmanager
from copy import deepcopy
import html
import json
import os
from pathlib import Path
import shutil

from tools import benchmark_capture as benchmark
from tools.audit_combat_loops import load, PHASES
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha, verify_capture

POLICIES = ('sustained-attacks', 'running-jumps')
BASE_SCENARIO = benchmark.scenario_for


def require_observer(core, system):
    marker = b'RCR_MAIN_STORE_TRACE' if system == 'snes' else b'RCR_NES_EVENT_TRACE'
    if marker not in core.read_bytes():
        raise ValueError('Core lacks required observer; refusing before capture')


def scenario(policy):
    if policy not in POLICIES:
        raise ValueError('Unknown combat policy')
    phases = deepcopy(BASE_SCENARIO('combat-knockdown-audio'))
    by_name = {p['name']: p for p in phases}
    by_name['idle']['frames'] += 90
    take = by_name['combat_take_hits']
    counter = by_name['combat_counterattack']
    take.update(frames=1440, buttons=['B'], pulse=[20, 5])
    counter.update(frames=1440, buttons=['A'], pulse=[20, 5])
    if policy == 'running-jumps':
        take.update(buttons=['Right', 'A', 'B'], pulse=[30, 24])
        counter.update(buttons=['Left', 'A', 'B'], pulse=[30, 24])
    return phases


@contextmanager
def installed(policy):
    wanted = 'combat-campaign-' + policy
    phases = scenario(policy)
    previous = benchmark.scenario_for
    def dispatch(name):
        return deepcopy(phases) if name == wanted else previous(name)
    benchmark.scenario_for = dispatch
    try:
        yield wanted
    finally:
        benchmark.scenario_for = previous


def capture(system, core, candidate, policy, observed, out):
    if any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Inherited observer/environment overrides are forbidden')
    trace = out.with_name(out.name + '.csv')
    if out.exists() or trace.exists():
        raise ValueError('Need fresh outputs')
    require_observer(core, system)
    rom = candidate/'native-cpu.sfc' if system == 'snes' else Path('roms/river-city-ransom-us.nes')
    paths = [Path(__file__), Path(benchmark.__file__), Path('tools/smoke_libretro.py'), core, rom]
    points = {}
    if system == 'snes':
        labels = candidate/'native_runtime.lbl'
        symbols = {s.split()[2].lstrip('.'): int(s.split()[1], 16) for s in labels.read_text().splitlines()}
        points = {0: symbols['gameplay_iteration_start'], 1: 0xf282,
                  2: symbols['camera_deferred_nmi_exit']+2, 3: 0xf2da}
        paths += [labels, candidate/'manifest.json', Path('tools/snes9x_main_store.inc'),
                  Path('.deps/snes9x/cpuexec.cpp')]
        if observed:
            os.environ['RCR_MAIN_STORE_TRACE'] = str(trace.resolve())
            for key, pc in points.items():
                os.environ[f'RCR_MAIN_STORE_PC{key}'] = f'{pc:04x}'
    else:
        points = {0: 0xf27d, 1: 0xf282, 2: 0xf2da}
        paths += [Path('tools/fceumm_queue_trace.inc'), Path('.deps/fceumm-raster/src/x6502.c')]
        if observed:
            os.environ.update(RCR_NES_EVENT_TRACE=str(trace.resolve()),
                RCR_NES_TRACE_FIRST='1', RCR_NES_TRACE_LAST=str(sum(p['frames'] for p in scenario(policy))))
            for key, pc in points.items():
                os.environ[f'RCR_NES_EVENT_PC{key}'] = f'{pc:04x}'
    sources = {str(p): sha(p) for p in paths}
    refs = {'menu': (Path('build/reference-title-05'), 600),
            'settings': (Path('build/reference-walk-02'), 600),
            'story': (Path('build/reference-walk-02'), 900),
            'street': (Path('build/reference-walk-02'), 1800)}
    try:
        with installed(policy) as name:
            benchmark.capture(core, rom, system, refs, out, name, True, True)
            receipt, _ = verify_capture(out)
        if not receipt['capture_complete']:
            raise ValueError('Incomplete encounter; evidence retained')
        if any(sha(Path(p)) != digest for p, digest in sources.items()):
            raise ValueError('Sources changed during capture')
        sources[str(out/'capture.json')] = sha(out/'capture.json')
        if observed:
            if not trace.stat().st_size:
                raise ValueError('Missing executed trace')
            sources[str(trace)] = sha(trace)
        binding = dict(policy=policy, system=system, observed=observed,
            points={str(k): f'{v:04x}' for k, v in points.items()},
            trace=str(trace) if observed else None, sources=sources,
            scope='Ordinary input only. Phase names are input requests, not proof of hits, death or pause.')
        (out/'combat-observer.json').write_text(json.dumps(binding, indent=2)+'\n')
    finally:
        for key in list(os.environ):
            if key.startswith('RCR_'):
                del os.environ[key]


def verify_pair(root, policy, system, candidate):
    normal, observed = (root/f'{policy}-{system}-{kind}' for kind in ('normal', 'observed'))
    for directory, enabled in ((normal, False), (observed, True)):
        binding = bound_report(directory/'combat-observer.json')
        if (binding['policy'], binding['system'], binding['observed']) != (policy, system, enabled):
            raise ValueError('Wrong capture policy/system/observer')
        if binding['sources'].get(str(Path(__file__))) != sha(Path(__file__)):
            raise ValueError('Unbound campaign implementation')
    with installed(policy):
        receipt, result, binding = load(observed, normal, system, candidate)
        normal_receipt, rows = verify_capture(normal)
    if receipt['core_sha256'] != normal_receipt['core_sha256']:
        raise ValueError('Observer-on/off controls must use the same core binary')
    # All full-RAM rows are authenticated, including non-traversal scenarios.
    import hashlib
    for row in rows:
        ram = bytes.fromhex(row['game_ram_hex'])
        if len(ram) != 2048 or hashlib.sha256(ram).hexdigest() != row['ram_sha256']:
            raise ValueError('Full RAM evidence mismatch')
    return receipt, result, rows, normal


def review(root, candidate, out):
    if out.exists():
        raise ValueError('Need fresh review')
    data, sources, cards = {}, {}, []
    out.mkdir(parents=True, exist_ok=False)
    for policy in POLICIES:
        data[policy] = {}
        receipts = []
        for system in ('nes', 'snes'):
            receipt, result, rows, normal = verify_pair(root, policy, system, candidate)
            receipts.append(receipt)
            data[policy][system] = result
            name = policy+'-'+system
            # Native whole-episode PCM, not normalized or resampled.
            shutil.copyfile(normal/'audio.wav', out/(name+'.wav'))
            figures = []
            for phase in ('combat_take_hits', 'combat_counterattack', 'combat_pause_wait', 'combat_resume_wait'):
                source = normal/(phase+'.png')
                dest = name+'-'+phase+'.png'
                shutil.copyfile(source, out/dest)
                figures.append(f'<figure><img src="{dest}"><figcaption>{html.escape(phase)}</figcaption></figure>')
            phase_table = ''.join(f'<tr><td>{p}</td><td>{r["iterations"]}</td>'
                f'<td>{html.escape(str(r["nmi_advances"]))}</td><td>{html.escape(str(r["start_frame_spans"]))}</td>'
                f'<td>{r["passed"]}</td></tr>' for p, r in result['phases'].items())
            cards.append(f'<section><h2>{name}: {"PASS" if result["passed"] else "FAIL"}</h2>'
                f'<p>{receipt["frames"]} frames; {len(result["other_off_cadence"])} off-cadence loops outside measured phases retained.</p>'
                '<table><tr><th>Requested phase</th><th>Loops</th><th>Ticks</th><th>Start spacing</th><th>Pass</th></tr>'
                +phase_table+f'</table><audio controls preload="none" src="{name}.wav"></audio><div class="grid">'
                +''.join(figures)+'</div></section>')
            for kind in ('normal', 'observed'):
                directory = root/f'{policy}-{system}-{kind}'
                binding = bound_report(directory/'combat-observer.json')
                sources.update(binding['sources'])
                sources[str(directory/'combat-observer.json')] = sha(directory/'combat-observer.json')
        if receipts[0]['scenario_sha256'] != receipts[1]['scenario_sha256']:
            raise ValueError('Different cross-system input policies')
    for name in (__file__, 'tools/audit_combat_loops.py', 'tools/audit_main_store_latency.py',
                 'tools/audit_route_loop_cadence.py', 'tools/nes_event_trace.py', 'tools/benchmark_report.py'):
        sources[str(Path(name))] = sha(Path(name))
    report = dict(passed=all(r['passed'] for p in data.values() for r in p.values()), runs=data,
        sources=sources, observer_neutral=True, physical_speed_verified=False, pop_free_verified=False,
        equal_encounters=False, release_ready=False,
        scope='Two independent input-only encounters per system. Every complete loop in seven phases, including pause/hit/transition states. No equal-enemy-state comparison or audio-fidelity verdict.')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Current combat campaign</title>'
        '<style>body{background:#101820;color:#eef;font:16px sans-serif;max-width:1200px;margin:auto;padding:24px}'
        'a{color:#7df}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}img{width:100%}'
        'figure{margin:0}td,th{padding:8px;border:1px solid #567}audio{width:100%}</style>'
        '<h1>Current cartridge: sustained combat campaign</h1><p>Cartridge SHA256: '+sha(candidate/'native-cpu.sfc')+'</p>'
        '<p>Input-only emulation. Traced runs exactly match independent untraced video, RAM, inputs and PCM. '
        'Phase names describe requests—not proof of hits or a successful pause. All failed timing observations remain in the report. '
        'NES and SNES enemies evolve independently: this is not a whole-game or hardware speed certification. '
        'Native audio is available for review, not graded pop-free.</p><p><a href="report.json">All loops and failures</a> · '
        '<a href="manifest.json">Artifact hashes</a></p>'+''.join(cards))
    (out/'manifest.json').write_text(json.dumps(dict(sources=sources,
        artifacts={p.name: sha(p) for p in out.iterdir() if p.is_file()}, release_ready=False), indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'], out=str(out))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    cap = sub.add_parser('capture')
    cap.add_argument('--system', choices=('nes', 'snes'), required=True)
    cap.add_argument('--policy', choices=POLICIES, required=True)
    cap.add_argument('--observed', action='store_true')
    for name in ('core', 'candidate', 'out'):
        cap.add_argument('--'+name, type=Path, required=True)
    rev = sub.add_parser('review')
    for name in ('root', 'candidate', 'out'):
        rev.add_argument('--'+name, type=Path, required=True)
    args = vars(parser.parse_args())
    command = args.pop('command')
    (capture if command == 'capture' else review)(**args)
