"""Observe actual guard admissions and production services across a full combat run."""
import argparse
import json
import os
from pathlib import Path

from tools import benchmark_capture as benchmark
from tools.benchmark_report import sha, verify_capture
from tools.capture_combat_instructions import equivalent
from tools.combat_campaign import installed


def points(candidate):
    symbols = lambda name: {r.split()[2].lstrip('.'): int(r.split()[1], 16)
                           for r in (candidate/name).read_text().splitlines()}
    runtime, boot = symbols('native_runtime.lbl'), symbols('native_boot.lbl')
    helper = (candidate/'guard.bin').read_bytes()
    service = runtime['second_tick_prepare_service']
    fallback = runtime['second_tick_prepare_fallback']
    jump = b'\x4c'+service.to_bytes(2, 'little')
    beam = bytes.fromhex('ad3f21ad3721')
    if helper.count(jump) != 1 or helper.count(beam) != 1:
        raise ValueError('Changed guard paths')
    # Final RTS follows the paired late-high PLA; exact shape is checked.
    done = helper.index(jump)+len(jump)+1
    if helper[done-1:done+1] != b'\x68\x60':
        raise ValueError('Changed guard return')
    image = (candidate/'native-cpu.sfc').read_bytes()
    if image[0x10000+service+20] != 0x60 or image[0x10000+fallback+16] != 0x60:
        raise ValueError('Changed service/fallback return')
    definitions = [('guard', '7f00'), ('pending_beam', f'{0x7F00+helper.index(beam):04x}'),
        ('admit', f'{0x7F00+helper.index(jump):04x}'), ('guard_return', f'{0x7F00+done:04x}'),
        ('service', f'{service:04x}'), ('service_return', f'{service+20:04x}'),
        ('fallback', f'{fallback:04x}'), ('fallback_return', f'{fallback+16:04x}'),
        ('producer', f'c0{boot["native_prepare"]:04x}'),
        ('palette', f'c0{boot["prepare_palette"]:04x}'),
        ('sprites', f'c0{boot["prepare_sprites"]:04x}'),
        ('tail', f'c0{boot["prepare_tail"]:04x}'),
        ('nmi', f'00{boot["nmi"]:04x}'),
        ('main_start', f'{runtime["gameplay_iteration_start"]:04x}'),
        ('main_finish', 'f2da'), ('enable', f'{runtime["camera_deferred_nmi_enable"]:04x}')]
    return [dict(index=i, name=name, pc=pc) for i, (name, pc) in enumerate(definitions)]


def capture(candidate, core, control, out):
    trace = out.with_suffix('.csv')
    if out.exists() or trace.exists() or any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Fresh outputs and clean observer environment required')
    if b'RCR_SPAN_TRACE' not in core.read_bytes():
        raise ValueError('Core has no span observer')
    sites = points(candidate)
    paths = [Path(__file__), Path('tools/capture_combat_instructions.py'),
        Path('tools/combat_campaign.py'), Path('tools/benchmark_capture.py'),
        Path('tools/smoke_libretro.py'), Path('tools/snes9x_span_trace.inc'),
        Path('.deps/snes9x/cpuexec.cpp'), candidate/'native-cpu.sfc', candidate/'manifest.json',
        candidate/'guard.bin', candidate/'native_runtime.lbl', candidate/'native_boot.lbl',
        control/'capture.json', core]
    sources = {str(p): sha(p) for p in paths}
    refs = {'menu': (Path('build/reference-title-05'), 600),
            'settings': (Path('build/reference-walk-02'), 600),
            'story': (Path('build/reference-walk-02'), 900),
            'street': (Path('build/reference-walk-02'), 1800)}
    try:
        with installed('sustained-attacks') as name:
            baseline, plain = verify_capture(control)
            if baseline['scenario_name'] != name:
                raise ValueError('Wrong control policy')
            os.environ.update(RCR_SPAN_TRACE=str(trace.resolve()), RCR_PROFILE_FIRST='1',
                              RCR_PROFILE_LAST=str(baseline['frames']))
            for site in sites:
                os.environ[f'RCR_SPAN_PC{site["index"]}'] = site['pc']
            benchmark.capture(core, candidate/'native-cpu.sfc', 'snes', refs, out, name, True, True)
            receipt, rows = verify_capture(out)
            equivalent(receipt, rows, baseline, plain)
        if any(sha(Path(p)) != h for p, h in sources.items()) or not trace.stat().st_size:
            raise ValueError('Changed source or missing trace')
        sources[str(trace)] = sha(trace)
        sources[str(out/'capture.json')] = sha(out/'capture.json')
        (out/'guard-spans.json').write_text(json.dumps(dict(sources=sources, points=sites,
            trace=str(trace), frames=receipt['frames'], observer_neutral=True,
            scope='Full sustained-attack episode; same-core full timeline/PCM equality. '
                  'Host-only exact PCs for admission, service/fallback, producer stages, NMI and main. '
                  'No emulated state writes, timers or added synchronization.'), indent=2)+'\n')
    finally:
        for name in list(os.environ):
            if name.startswith('RCR_'):
                del os.environ[name]


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'core', 'control', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    capture(**vars(p.parse_args()))
