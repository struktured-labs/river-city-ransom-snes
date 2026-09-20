"""Boot through right_08 for audio scheduling tests; explicit prefix, no state edits."""
import argparse
import csv
import json
import os
from pathlib import Path
import time
import wave
import numpy as np
from PIL import Image
from tools import benchmark_capture as bench
from tools.benchmark_report import sha, verify_capture
from tools.capture_combat_instructions import equivalent
from tools.capture_sprite_prefix import installed_prefix

LAST_PHASE = 'right_08'


def compare_full_prefix(short, full, folder):
    if not short or len(short) >= len(full):
        raise ValueError('Not a proper nonempty prefix')
    policy = bench.waypoint_policy('traversal-park-single-sweep')
    for a, b in zip(short, full):
        # Full-route harness records this image-derived diagnostic even before
        # waypoint inputs begin. Recompute it from the actual prefix frame;
        # do not remove or ignore the full run's field.
        actual = dict(a)
        with Image.open(folder / a['frame_image']) as im:
            actual['waypoint_cursor'] = list(policy.cursor_mask(np.asarray(im.convert('RGB'))))
        if actual != b:
            raise ValueError(f'Changed prefix frame {a["frame"]}')


def capture(candidate, core, out, full=None, control=None):
    started = time.monotonic()
    if out.exists() or any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Fresh path and clean observer environment required')
    if full is not None and control is not None:
        raise ValueError('Use full control or prefix control, not both')
    rom = candidate / 'native-cpu.sfc'
    sources = {str(p): sha(p) for p in (Path(__file__), Path('tools/capture_sprite_prefix.py'),
        Path('tools/benchmark_capture.py'), Path('tools/benchmark_report.py'),
        Path('tools/capture_combat_instructions.py'), Path('tools/snes9x_main_store.inc'),
        Path('tools/traversal_waypoints.py'), core.parent.parent / 'cpuexec.cpp',
        core, rom, candidate / 'manifest.json')}
    baseline = previous = None
    if full is not None:
        baseline, previous = verify_capture(full)
    elif control is not None:
        with installed_prefix(LAST_PHASE):
            baseline, previous = verify_capture(control)
    if baseline is not None:
        if baseline['rom_sha256'] != sha(rom) or baseline['core_sha256'] != sha(core):
            raise ValueError('Different ROM/core control')
        for name in ('capture.json', 'timeline.json', 'audio.wav'):
            p = (full if full is not None else control) / name
            sources[str(p)] = sha(p)
    verification_before = time.monotonic() - started
    traces = {}
    env = {}
    if control is not None:
        for key, suffix in (('RCR_MAIN_STORE_TRACE', '-service.csv'),
                ('RCR_DSP_LATENCY_TRACE', '-dsp.csv'), ('RCR_DSP_DAC_PCM', '-dac.pcm'),
                ('RCR_AUDIO_BUS_TRACE', '-bus.csv')):
            trace = out.with_name(out.name + suffix)
            if trace.exists():
                raise ValueError('Trace exists')
            traces[key] = trace
            env[key] = str(trace.resolve())
        env.update({f'RCR_MAIN_STORE_PC{k}': f'{pc:04x}' for k, pc in
                    enumerate((0xfa54, 0xfa64, 0x5f00, 0x7885))})
    refs = dict(menu=(Path('build/reference-title-05'), 600),
                settings=(Path('build/reference-walk-02'), 600),
                story=(Path('build/reference-walk-02'), 900),
                street=(Path('build/reference-walk-02'), 1800))
    replay = time.monotonic()
    try:
        os.environ.update(env)
        with installed_prefix(LAST_PHASE):
            bench.capture(core, rom, 'snes', refs, out, 'traversal-park-single-sweep', True, True)
    finally:
        for key in env:
            os.environ.pop(key, None)
    replay_seconds = time.monotonic() - replay
    verification = time.monotonic()
    with installed_prefix(LAST_PHASE):
        receipt, rows = verify_capture(out)
    if not receipt['capture_complete'] or any(r['fault'] or r['input_requested'] != r['input_delivered'] for r in rows):
        raise ValueError('Incomplete/faulty prefix')
    if control is not None:
        equivalent(receipt, rows, baseline, previous)
    if full is not None:
        compare_full_prefix(rows, previous, out)
        with wave.open(str(out / 'audio.wav')) as a, wave.open(str(full / 'audio.wav')) as b:
            if ((a.getnchannels(), a.getsampwidth(), a.getframerate()) !=
                    (b.getnchannels(), b.getsampwidth(), b.getframerate()) or
                    a.readframes(a.getnframes()) != b.readframes(a.getnframes())):
                raise ValueError('Changed native audio prefix')
    for path in traces.values():
        if not path.stat().st_size:
            raise ValueError('Empty trace')
        sources[str(path)] = sha(path)
    for name in ('capture.json', 'timeline.json', 'audio.wav'):
        sources[str(out / name)] = sha(out / name)
    if any(sha(p) != h for p, h in sources.items()):
        raise ValueError('Source changed')
    report = dict(sources=sources, frames=len(rows), last_phase=LAST_PHASE,
        observer_neutral=control is not None, full_prefix_equal=full is not None,
        traces={k: str(p) for k, p in traces.items()},
        control=str(control) if control else None, full=str(full) if full else None,
        timing=dict(replay_seconds=replay_seconds, verify_before_seconds=verification_before,
                    verify_after_seconds=time.monotonic() - verification,
                    total_seconds=time.monotonic() - started),
        scope=__doc__ + ' Full-reference comparison recomputes waypoint_cursor from each '
        'actual prefix image; all other primary fields and every native PCM sample compare exactly.')
    (out / 'audio-prefix.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('frames', 'observer_neutral', 'full_prefix_equal', 'timing')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'core', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    for name in ('full', 'control'):
        parser.add_argument('--' + name, type=Path)
    capture(**vars(parser.parse_args()))
