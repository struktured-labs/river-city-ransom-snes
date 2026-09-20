"""2P combat span windows around a measured three-frame stall."""
import argparse
import json
import os
from pathlib import Path
from tools import benchmark_capture as benchmark
from tools.benchmark_report import sha, verify_capture
from tools.capture_combat_instructions import capture as capture_instructions, equivalent
from tools.combat_campaign import installed
from tools.two_player_combat import installed_policy, two_ports

SPAN_PCS = {
    'RCR_SPAN_PC0': '31f7',   # gameplay_iteration_start
    'RCR_SPAN_PC1': 'f282',   # original input call
    'RCR_SPAN_PC2': '323d',   # camera_deferred_nmi_exit+2
    'RCR_SPAN_PC3': 'f2da',   # original loop finish
    'RCR_SPAN_PC4': 'd253',   # wait_port0
    'RCR_SPAN_PC5': 'd290',   # @send
    'RCR_SPAN_PC6': 'f000',   # beam-deadline helper
    'RCR_SPAN_PC7': '2128',   # native_sound_commit
}


def capture(core, candidate, policy, out, control=None, first=None, last=None):
    frames = []
    observed = control is not None
    if not observed:
        with installed_policy(), two_ports(core, frames):
            capture_instructions(core, candidate, policy, out, control, first, last)
        return
    if any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Inherited instrumentation overrides forbidden')
    if b'RCR_SPAN_TRACE' not in core.read_bytes():
        raise ValueError('Span observer missing from core')
    if not 1 <= first <= last:
        raise ValueError('Invalid span window')
    trace = out.with_suffix('.csv')
    if out.exists() or trace.exists():
        raise ValueError('Fresh outputs required')
    rom = candidate / 'native-cpu.sfc'
    sources = [Path(__file__), Path('tools/combat_campaign.py'), Path('tools/two_player_combat.py'),
               Path('tools/benchmark_capture.py'), Path('tools/snes9x_span_trace.inc'),
               core, rom, candidate / 'manifest.json', control / 'capture.json']
    hashes = {str(p): sha(p) for p in sources}
    refs = {'menu': (Path('build/reference-title-05'), 600),
            'settings': (Path('build/reference-walk-02'), 600),
            'story': (Path('build/reference-walk-02'), 900),
            'street': (Path('build/reference-walk-02'), 1800)}
    env = dict(RCR_SPAN_TRACE=str(trace.resolve()), RCR_PROFILE_FIRST=str(first),
               RCR_PROFILE_LAST=str(last), **SPAN_PCS)
    try:
        os.environ.update(env)
        with installed_policy(), two_ports(core, frames), installed(policy) as name:
            baseline, rows0 = verify_capture(control)
            if last > baseline['frames'] or baseline['scenario_name'] != name:
                raise ValueError('Window or policy outside control')
            benchmark.capture(core, rom, 'snes', refs, out, name, True, True)
            receipt, rows = verify_capture(out)
            equivalent(receipt, rows, baseline, rows0)
        if not trace.stat().st_size:
            raise ValueError('Missing span trace')
        hashes[str(trace)] = sha(trace)
        hashes[str(out / 'capture.json')] = sha(out / 'capture.json')
        (out / 'span-control.json').write_text(json.dumps(dict(
            sources=hashes, observer_neutral=True, policy=policy, first=first, last=last,
            pcs=SPAN_PCS, scope=__doc__), indent=2) + '\n')
        print(json.dumps(dict(out=str(out), frames=receipt['frames'], complete=True)))
    finally:
        for key in list(env):
            os.environ.pop(key, None)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('core', 'candidate', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--policy', required=True)
    p.add_argument('--control', type=Path)
    for name in ('first', 'last'):
        p.add_argument('--' + name, type=int)
    capture(**vars(p.parse_args()))
