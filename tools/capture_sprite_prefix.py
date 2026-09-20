"""Short, boot-driven prefix replay for sprite publication (no state edits)."""
import argparse
import json
import os
from pathlib import Path
import time
from contextlib import contextmanager

from tools import benchmark_capture as bench
from tools.audit_main_display_latency import bound_report
from tools.audio_packet_log import labels
from tools.benchmark_report import sha, verify_capture
from tools.capture_combat_instructions import equivalent
from tools.build_sprite_copy_prepare import PREIMAGE, REPLACEMENT


@contextmanager
def installed_prefix(last_phase='right_04'):
    original = bench.scenario_for
    scenario = original('traversal-park-single-sweep')
    end = next(i for i, p in enumerate(scenario) if p['name'] == last_phase)
    prefix = scenario[:end+1]
    if any('waypoint' in p for p in prefix): raise ValueError('Prefix must end before waypoint policy')
    try:
        bench.scenario_for = lambda name: prefix if name == 'traversal-park-single-sweep' else original(name)
        yield
    finally:
        bench.scenario_for = original


def capture(candidate, out, control=None, observed=False, first=1978, last=2020, last_phase='right_04', verify_existing=False):
    started = time.monotonic()
    build = Path('.deps/snes9x-sprite-events-3243')
    proof = bound_report(build/'sprite-event-build.json'); core = Path(proof['core'])
    trace = out.with_suffix('.csv')
    if (out.exists() and not verify_existing) or trace.exists() or any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Fresh output and clean observer environment required')
    if verify_existing and (observed or (out/'sprite-events-capture.json').exists()):
        raise ValueError('Recovery only verifies unpublished normal captures')
    if sha(core) != proof['core_sha256']: raise ValueError('Changed observer core')
    for p, h in proof['artifacts'].items():
        if sha(build/p) != h: raise ValueError('Changed observer source')
    if observed and control is None: raise ValueError('Same-core normal control required')
    boot = labels(candidate/'native_boot.lbl'); runtime = labels(candidate/'native_runtime.lbl')
    points = dict(S=runtime['@dma_copied'], P=boot['prepare_sprites'], T=boot['prepare_tail'])
    meta = json.loads((candidate/'manifest.json').read_text()); image = (candidate/'native-cpu.sfc').read_bytes()
    if sha(candidate/'native-cpu.sfc') != meta['rom_sha256']: raise ValueError('Changed candidate')
    original = Path('build/tail-startup-pitch-game-3219/native-cpu.sfc').read_bytes()
    for key, at in points.items():
        for offset in ([bank*65536+at for bank in range(1, 9)] if key == 'S' else [at]):
            expected = REPLACEMENT+original[offset+9:offset+12] if key == 'S' and meta.get('experimental_sprite_copy_prepare') else original[offset:offset+12]
            if image[offset:offset+12] != expected: raise ValueError('Changed event hook')
    scenario_name = 'traversal-park-single-sweep'
    sources = dict(proof['sources'])
    for p in (Path(__file__), Path('tools/benchmark_capture.py'), Path('tools/benchmark_report.py'),
        Path('tools/build_sprite_copy_prepare.py'), Path('tools/audio_packet_log.py'),
        build/'sprite-event-build.json', core, candidate/'native-cpu.sfc', candidate/'manifest.json',
        candidate/'native_boot.lbl', candidate/'native_runtime.lbl',
        Path('build/tail-startup-pitch-game-3219/native-cpu.sfc')):
        sources[str(p)] = sha(p)
    env = {}
    if observed:
        env = dict(RCR_SPRITE_EVENT_TRACE=str(trace.resolve()), RCR_SPRITE_FIRST=str(first),
            RCR_SPRITE_LAST=str(last), RCR_SPRITE_SOURCE_PC=f'{points["S"]:04x}',
            RCR_SPRITE_PREPARE_PC=f'{points["P"]:04x}', RCR_SPRITE_DONE_PC=f'{points["T"]:04x}')
    refs = dict(menu=(Path('build/reference-title-05'), 600), settings=(Path('build/reference-walk-02'), 600),
        story=(Path('build/reference-walk-02'), 900), street=(Path('build/reference-walk-02'), 1800))
    try:
        os.environ.update(env)
        if not verify_existing:
            with installed_prefix(last_phase):
                bench.capture(core, candidate/'native-cpu.sfc', 'snes', refs, out, scenario_name,
                    frame_images=True, full_ram_telemetry=True)
    finally:
        for key in env: os.environ.pop(key, None)
    with installed_prefix(last_phase): receipt, rows = verify_capture(out)
    if (receipt['rom_sha256'] != sha(candidate/'native-cpu.sfc') or receipt['core_sha256'] != sha(core)
        or receipt['capture_tool_sha256'] != sha(Path('tools/benchmark_capture.py'))):
        raise ValueError('Wrong capture ROM/core/tool')
    if not receipt['capture_complete'] or not 1 <= first <= last <= len(rows):
        raise ValueError('Incomplete prefix/window')
    if any(r['fault'] or r['input_requested'] != r['input_delivered'] for r in rows):
        raise ValueError('Faulty prefix execution')
    if observed:
        with installed_prefix(last_phase): before, previous = verify_capture(control)
        equivalent(receipt, rows, before, previous)
        if not trace.stat().st_size: raise ValueError('Missing sprite events')
        for p in (trace, control/'capture.json', control/'timeline.json', control/'audio.wav'):
            sources[str(p)] = sha(p)
    for p in (out/'capture.json', out/'timeline.json', out/'audio.wav'): sources[str(p)] = sha(p)
    if any(sha(Path(p)) != h for p, h in sources.items()): raise ValueError('Changed source')
    report = dict(rom_sha256=receipt['rom_sha256'], observed=observed, observer_neutral=observed,
        sources=sources, reference=str(control) if control else None, first=first, last=last, points=points,
        trace=str(trace) if observed else None, elapsed_seconds=time.monotonic()-started,
        verified_existing_capture=verify_existing, last_phase=last_phase,
        scope=__doc__+' Original scenario explicitly truncated after '+last_phase+'. '
        'P/T cover the original full producer, not the new direct sprite helper. '
        'D/E/R retain actual full OAM transfer/render observations for both paths.')
    (out/'sprite-events-capture.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(out=str(out), frames=len(rows), seconds=report['elapsed_seconds'], observed=observed)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'out'): p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--control', type=Path); p.add_argument('--observed', action='store_true')
    p.add_argument('--verify-existing', action='store_true')
    p.add_argument('--last-phase', default='right_04')
    for name, default in (('first', 1978), ('last', 2020)): p.add_argument('--'+name, type=int, default=default)
    capture(**vars(p.parse_args()))
