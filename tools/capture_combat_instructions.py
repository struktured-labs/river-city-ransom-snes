"""Fresh-process instruction windows for the unchanged combat input policies."""
import argparse
import json
import os
from pathlib import Path

from tools import benchmark_capture as benchmark
from tools.benchmark_report import sha, verify_capture
from tools.combat_campaign import installed, POLICIES


def equivalent(receipt, rows, baseline, control):
    for key in ('system', 'rom_sha256', 'core_sha256', 'scenario_sha256',
                'frames', 'audio_sha256'):
        if receipt[key] != baseline[key]:
            raise ValueError('Instruction observer changed control: '+key)
    if not receipt['capture_complete'] or not baseline['capture_complete'] or rows != control:
        raise ValueError('Incomplete capture or changed full timeline')
    if any(r['fault'] or r['input_requested'] != r['input_delivered'] for r in rows):
        raise ValueError('Faulty capture or input mismatch')


def capture(core, candidate, policy, out, control=None, first=None, last=None):
    observed = control is not None
    if observed != (first is not None and last is not None):
        raise ValueError('Control and both instruction-window bounds required together')
    if not observed and (first is not None or last is not None):
        raise ValueError('Partial instruction window')
    if observed and not 1 <= first <= last:
        raise ValueError('Invalid instruction window')
    if any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Inherited instrumentation overrides forbidden')
    trace = out.with_suffix('.csv')
    if out.exists() or trace.exists():
        raise ValueError('Fresh outputs required')
    if b'RCR_INSTRUCTION_TRACE' not in core.read_bytes():
        raise ValueError('Instruction observer missing from core')
    rom = candidate/'native-cpu.sfc'
    sources = [Path(__file__), Path('tools/combat_campaign.py'),
        Path('tools/benchmark_capture.py'), Path('tools/smoke_libretro.py'),
        Path('tools/snes9x_instruction_trace.inc'), Path('.deps/snes9x/cpuexec.cpp'),
        core, rom, candidate/'manifest.json', candidate/'native_boot.lbl',
        candidate/'native_runtime.lbl']
    if observed:
        sources.append(control/'capture.json')
    hashes = {str(p): sha(p) for p in sources}
    refs = {'menu': (Path('build/reference-title-05'), 600),
        'settings': (Path('build/reference-walk-02'), 600),
        'story': (Path('build/reference-walk-02'), 900),
        'street': (Path('build/reference-walk-02'), 1800)}
    try:
        with installed(policy) as name:
            if observed:
                baseline, rows0 = verify_capture(control)
                if last > baseline['frames'] or baseline['scenario_name'] != name:
                    raise ValueError('Window or policy outside control')
                os.environ.update(RCR_INSTRUCTION_TRACE=str(trace.resolve()),
                    RCR_PROFILE_FIRST=str(first), RCR_PROFILE_LAST=str(last))
            benchmark.capture(core, rom, 'snes', refs, out, name, True, True)
            receipt, rows = verify_capture(out)
            equivalent(receipt, rows, baseline if observed else receipt,
                       rows0 if observed else rows)
        if any(sha(Path(p)) != d for p, d in hashes.items()):
            raise ValueError('Source changed during execution')
        if observed:
            if not trace.stat().st_size or receipt['instruction_trace']['sha256'] != sha(trace):
                raise ValueError('Missing or changed instruction trace')
            hashes[str(trace)] = sha(trace)
        hashes[str(out/'capture.json')] = sha(out/'capture.json')
        (out/'instruction-control.json').write_text(json.dumps(dict(sources=hashes,
            observer_neutral=observed, policy=policy, first=first, last=last,
            scope='Unchanged input-only combat policy; same-core full timeline and PCM control. '
                  'Instruction elapsed clocks include DMA and interrupts.'), indent=2)+'\n')
    finally:
        for key in ('RCR_INSTRUCTION_TRACE', 'RCR_PROFILE_FIRST', 'RCR_PROFILE_LAST'):
            os.environ.pop(key, None)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('core', 'candidate', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--policy', choices=POLICIES, required=True)
    p.add_argument('--control', type=Path)
    for name in ('first', 'last'):
        p.add_argument('--'+name, type=int)
    capture(**vars(p.parse_args()))
