"""Fresh source/preparation/OAM DMA/render events with exact same-core control."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from tools.audit_main_display_latency import bound_report
from tools.audio_packet_log import labels
from tools.benchmark_report import sha, verify_capture


def capture(build, candidate, reference, out, first, last, observed=False):
    trace = out.with_suffix('.csv')
    if out.exists() or trace.exists() or any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Fresh output and clean instrumentation environment required')
    proof = bound_report(build/'sprite-event-build.json'); core = Path(proof['core'])
    if sha(core) != proof['core_sha256']:
        raise ValueError('Changed core')
    for p, h in proof['artifacts'].items():
        if sha(build/p) != h: raise ValueError('Changed generated observer')
    baseline, before = verify_capture(reference)
    if not 1 <= first <= last <= baseline['frames'] or baseline['rom_sha256'] != sha(candidate/'native-cpu.sfc'):
        raise ValueError('Wrong cartridge or invalid observation window')
    if observed and baseline['core_sha256'] != sha(core):
        raise ValueError('Same-core unobserved control required')
    boot = labels(candidate/'native_boot.lbl'); runtime = labels(candidate/'native_runtime.lbl')
    points = dict(S=runtime['@dma_copied'], P=boot['prepare_sprites'], T=boot['prepare_tail'])
    image = (candidate/'native-cpu.sfc').read_bytes()
    # Retain exact bytes at the bound PCs; the CPU code must match the parent
    # qualified by this window experiment, not arbitrary inherited label names.
    parent = Path('build/ordinary-early-audio-trial-3065')
    old = (parent/'native-cpu.sfc').read_bytes()
    for k, pc in points.items():
        offsets = [bank*0x10000+pc for bank in range(1, 9)] if k == 'S' else [pc]
        if any(image[at:at+12] != old[at:at+12] for at in offsets):
            raise ValueError('Changed source/preparation hook instructions')
    sources = dict(proof['sources'])
    for p in (Path(__file__), Path('tools/benchmark_capture.py'), Path('tools/benchmark_report.py'),
              Path('tools/audio_packet_log.py'), build/'sprite-event-build.json', core,
              candidate/'native-cpu.sfc', candidate/'manifest.json', candidate/'native_boot.lbl',
              candidate/'native_runtime.lbl', parent/'native-cpu.sfc',
              reference/'capture.json', reference/'timeline.json', reference/'audio.wav'):
        sources[str(p)] = sha(p)
    env = os.environ.copy()
    if observed:
        env.update(RCR_SPRITE_EVENT_TRACE=str(trace.resolve()), RCR_SPRITE_FIRST=str(first),
            RCR_SPRITE_LAST=str(last), RCR_SPRITE_SOURCE_PC=f'{points["S"]:04x}',
            RCR_SPRITE_PREPARE_PC=f'{points["P"]:04x}', RCR_SPRITE_DONE_PC=f'{points["T"]:04x}')
    subprocess.run([sys.executable, '-m', 'tools.benchmark_capture', '--system', 'snes',
        '--core', str(core), '--rom', str(candidate/'native-cpu.sfc'), '--title', 'build/reference-title-05',
        '--walk', 'build/reference-walk-02', '--scenario', baseline['scenario_name'],
        '--frame-images', '--full-ram-telemetry', '--out', str(out)], env=env, check=True)
    receipt, rows = verify_capture(out)
    if (not receipt['capture_complete'] or not baseline['capture_complete'] or rows != before
        or any(receipt[k] != baseline[k] for k in ('rom_sha256', 'scenario_sha256', 'frames', 'audio_sha256'))
        or any(r['fault'] or r['input_requested'] != r['input_delivered'] for r in rows)):
        raise ValueError('Non-neutral/faulty execution')
    if observed:
        if not trace.stat().st_size: raise ValueError('Missing event trace')
        sources[str(trace)] = sha(trace)
    for p in (out/'capture.json', out/'timeline.json', out/'audio.wav'):
        sources[str(p)] = sha(p)
    if any(sha(Path(p)) != h for p, h in sources.items()):
        raise ValueError('Source changed during capture')
    report = dict(rom_sha256=receipt['rom_sha256'], observed=observed, observer_neutral=observed,
        sources=sources, reference=str(reference), first=first, last=last, points=points,
        trace=str(trace) if observed else None,
        scope=__doc__+' Normal new-core execution also reproduces the prior core. '
              'S is after translated NES DMA copy; P/T surround sprite preparation; '
              'D/E surround actual general OAM DMA; R records OAM before main-screen rendering. '
              'Only this selected frame window is instrumented, not full-route publication coverage.')
    (out/'sprite-events-capture.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(observed=observed, first=first, last=last, frames=len(rows), identical=True)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('build', 'candidate', 'reference', 'out'): p.add_argument('--'+name, type=Path, required=True)
    for name in ('first', 'last'): p.add_argument('--'+name, type=int, required=True)
    p.add_argument('--observed', action='store_true')
    capture(**vars(p.parse_args()))
